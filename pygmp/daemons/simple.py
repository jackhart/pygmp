"""Implementation of a static multicast routing daemon.

    Inspired and modeled after https://github.com/troglobit/smcroute
"""
#  MIT License
#
#  Copyright (c) 2023 Jack Hart
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to deal
#  in the Software without restriction, including without limitation the rights
#  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#  copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all
#  copies or substantial portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#  SOFTWARE.
from __future__ import annotations

import ipaddress
from ipaddress import IPv4Address, IPv4Network
import threading
from pygmp.daemons.utils import get_logger
from pygmp.daemons.config import load_config, MRoute
from pygmp import kernel, data


logger = get_logger(__name__)

ANY_ADDR = "0.0.0.0"  # TODO - get constant from C extension
BUFFER_SIZE = 6000  # TODO - think through buffer size


def main(sock, args, app):
    config = load_config(args.config)
    kernel.flush(sock)
    kernel.disable_pim(sock)
    kernel.enable_mrt(sock)

    vif_manager = VifManager(sock, config.phyint)
    mfc_manager = MfcManager(sock, vif_manager, config.mroute)
    control_msg_handler = ControlMessageHandler(sock, mfc_manager, vif_manager)

    app = setup_app(app, vif_manager, mfc_manager, control_msg_handler)
    _ = start_socket_listener(sock, control_msg_handler)

    return app


def setup_app(app, vif_manager, mfc_manager, control_msg_handler):
    # Avoid importing FastAPI types at module import time so the core library can
    # still be imported without optional daemon dependencies.
    from fastapi import HTTPException

    @app.get("/vifs")
    def vifs():
        return vif_manager.vifs()

    @app.get("/vifs/{interface_name}")
    def vifs_by_name(interface_name: str):
        try:
            return vif_manager.vifs()[interface_name]
        except KeyError as e:
            raise HTTPException(status_code=404, detail=f"VIF '{interface_name}' not found") from e

    @app.get("/static_mfc")
    def static_mfc():
        return mfc_manager.static_mfc()

    @app.get("/static_mfc/{vif_index}")
    def static_mfc_by_vifi(vif_index: int):
        try:
            return mfc_manager.static_mfc()[vif_index]
        except KeyError as e:
            raise HTTPException(status_code=404, detail=f"No static MFC entries for VIF {vif_index}") from e

    @app.get("/dynamic_mfc")
    def dynamic_mfc():
        return mfc_manager.dynamic_mfc()

    @app.get("/dynamic_mfc/{vif_index}")
    def dynamic_mfc_by_vifi(vif_index: int):
        try:
            return mfc_manager.dynamic_mfc()[vif_index]
        except KeyError as e:
            raise HTTPException(status_code=404, detail=f"No dynamic routes for VIF {vif_index}") from e

    @app.post("/vifs")
    def add_vif(interface_address_or_index: IPv4Address | int, mcast_index: int | None = None):
        interfaces = kernel.network_interfaces()
        if isinstance(interface_address_or_index, IPv4Address):
            match = next((interface for interface in interfaces.values()
                          if str(interface_address_or_index) in interface.addresses), None)
            if not match:
                raise ValueError(f"Could not find interface with address {interface_address_or_index}.")
        else:
            match = next((interface for interface in interfaces.values()
                            if interface.index == interface_address_or_index), None)
            if not match:
                raise ValueError(f"Could not find interface with index {interface_address_or_index}.")

        vif_manager.add(match, mcast_index)
        return vif_manager.vifs()[match.name]

    @app.delete("/vifs/{interface_name}")
    def delete_vif(interface_name_or_index: str | int):
        if isinstance(interface_name_or_index, str):
            vif_manager.remove_by_name(interface_name_or_index)
        else:
            vif_manager.remove_by_index(interface_name_or_index)

    # TODO - POST and DELETE mfc
    @app.post("/mfc")
    def add_mfc(mroute: dict):
        mr = _mroute_from_payload(mroute)
        mfc_manager.add(mr)
        # For wildcard routes we only store config; for explicit sources we program the kernel.
        if str(mr.source) == ANY_ADDR:
            return mr
        return {"status": "ok"}

    @app.delete("/mfc")
    def delete_mfc(mroute: dict):
        mr = _mroute_from_payload(mroute)
        mfc_manager.remove(mr)
        return {"status": "ok"}

    return app


class VifManager:
    # FIXME - VIF can represent a physical interface OR an addresses.
    #  (The address does not imply the src address of a packet, but rather, the IP address on an interface.)
    def __init__(self, sock: kernel.InetRawSocketType, phyint: list[data.Interface] | None = None):
        self.sock = sock
        self._vif_name_list = list(self.vifs().keys())
        if phyint:
            for i, interf in enumerate(phyint):
                self.add(interf, i)

    def vifs(self) -> dict[str, data.VIFTableEntry]:
        """Returns a dictionary of the virtual multicast interfaces registered in the kernel."""
        vif_table = {entry.name: entry for entry in kernel.ip_mr_vif()}
        return vif_table

    def vifi(self, name) -> int:
        """Returns the multicast VIF index for the given interface."""
        try:
            return self._vif_name_list.index(name)
        except ValueError as e:
            raise ValueError(f"Could not find index for Interface {name}.") from e

    def add(self, interf: data.Interface, mcast_index: int | None = None):
        """Adds a virtual multicast interface to the kernel.
            If index is provided, it is used and the interface is not checked for existence before adding.
        """
        if mcast_index is None:
            vifs = self.vifs()
            if interf.name in vifs:
                raise ValueError(f"Interface {interf.name} already exists.")
            mcast_index = len(vifs)
        kernel.add_vif(self.sock, data.VifCtl(vifi=mcast_index, lcl_addr=int(interf.index)))
        self._vif_name_list = list(self.vifs().keys())

    def remove_by_index(self, mc_index: int):
        """Removes a virtual multicast interface from the kernel by multicast index."""
        vifctl = data.VifCtl(vifi=mc_index, lcl_addr=ANY_ADDR)
        kernel.del_vif(self.sock, vifctl)
        self._vif_name_list = list(self.vifs().keys())

    def remove_by_name(self, interface_name: str):
        """Removes a virtual multicast interface from the kernel by name."""
        try:
            vif_entry = self.vifs()[interface_name]
        except KeyError as e:
            raise ValueError(f"Interface {interface_name} does not exist.") from e
        # FIXME - interface vs address
        kernel.del_vif(self.sock, data.VifCtl(vifi=vif_entry.index, lcl_addr=vif_entry.local_addr_or_interface))

    def make_ttls_list(self, phyints: dict[str | int, int]):
        ttls = [0] * len(self._vif_name_list)
        for inter, ttl in phyints.items():
            if isinstance(inter, str):
                inter = self.vifi(inter)
            try:
                ttls[inter] = ttl
            except IndexError as e:
                raise ValueError(f"Interface of index {inter} does not exist.") from e
        return ttls


class MfcManager:
    def __init__(self, sock, vif_manager, mroute_list: list[MRoute] | None = None):
        self.sock = sock
        self.vif_manager = vif_manager
        # wildcard routes keyed by incoming VIF index, populated from config where source == 0.0.0.0
        self._dynamic_mroutes: dict[int, list[MRoute]] = {}
        if mroute_list:
            for mroute in mroute_list:
                self.add(mroute)

    def static_mfc(self) -> dict[int, list[data.MFCEntry]]:
        result = {}
        for entry in kernel.ip_mr_cache():
            if result.get(entry.iif):
                result[entry.iif].append(entry)
            else:
                result[entry.iif] = [entry]
        return result

    def dynamic_mfc(self) -> dict[int, list[MRoute]]:
        return self._dynamic_mroutes

    def add(self, mroute: MRoute):
        # Group prefixes cannot be installed directly into the kernel MFC; they must be
        # expanded on-demand as (S,G) entries when NOCACHE messages arrive.
        if isinstance(mroute.group, (IPv4Network,)) and str(mroute.source) != ANY_ADDR:
            raise ValueError("mroute group prefixes require source=0.0.0.0 (wildcard source)")

        if str(mroute.source) == ANY_ADDR or isinstance(mroute.group, (IPv4Network,)):
            vifi = self.vif_manager.vifi(mroute.from_)
            routes = self._dynamic_mroutes.setdefault(vifi, [])
            # Replace existing entry for the same group/prefix.
            for idx, existing in enumerate(routes):
                if existing.group == mroute.group:
                    routes[idx] = mroute
                    break
            else:
                routes.append(mroute)
        else:
            self._add_mfc_syscall(mroute)

    def remove(self, mroute: MRoute):
        parent = self.vif_manager.vifi(mroute.from_)
        if str(mroute.source) == ANY_ADDR:
            if self._dynamic_mroutes.get(parent):
                self._dynamic_mroutes[parent].remove(mroute)
                if not self._dynamic_mroutes[parent]:
                    del self._dynamic_mroutes[parent]
            else:
                raise ValueError(f"Dynamic MRoute {mroute} does not exist.")
        else:
            kernel.del_mfc(self.sock, data.MfcCtl(origin=mroute.source, mcastgroup=mroute.group, parent=parent, ttls=[]))

    def match(self, vifi: int, group: IPv4Address, source_address: IPv4Address) -> data.MFCEntry | MRoute | None:
        """Find a matching route for an incoming (vifi, (S,G)).

        Preference order:
        - Exact (S,G) installed in-kernel (static routes from config with an explicit source)
        - Wildcard (*,G) configured routes (source == 0.0.0.0), matched by exact group or group prefix
        """
        try:
            static = self.static_mfc().get(vifi, [])
            exact = next((route for route in static
                          if str(route.group) == str(group) and str(route.origin) == str(source_address)), None)
            if exact:
                return exact

            dynamic = self.dynamic_mfc().get(vifi, [])
            return next((route for route in dynamic if _group_matches(route.group, group)), None)
        except KeyError:
            return None

    def _add_mfc_syscall(self, mroute: MRoute):
        mfcctl = data.MfcCtl(origin=mroute.source,
                             mcastgroup=mroute.group,
                             parent=self.vif_manager.vifi(mroute.from_), 
                             ttls=self.vif_manager.make_ttls_list(mroute.to))
        kernel.add_mfc(self.sock, mfcctl)


class ControlMessageHandler:
    def __init__(self, sock, mfc_manager: MfcManager, vif_manager: VifManager):
        self.sock = sock
        self.mfc_manager = mfc_manager
        self.vif_manager = vif_manager

    def process_control_message(self, message: data.IGMPControl):
        if message.msgtype == data.ControlMsgType.IGMPMSG_NOCACHE:
            match = self.mfc_manager.match(message.vif, message.im_dst, message.im_src)
            if match:
                # match may be an installed kernel entry (MFCEntry) or a wildcard configured route (MRoute)
                if isinstance(match, data.MFCEntry):
                    oifs = match.oifs
                else:
                    oifs = match.to

                ttls_list = self.vif_manager.make_ttls_list(oifs)
                mfctl = data.MfcCtl(origin=message.im_src, mcastgroup=message.im_dst, parent=message.vif, ttls=ttls_list)
                kernel.add_mfc(self.sock, mfctl)
        # TODO - expand support
        else:
            raise ValueError(f"Unknown control message type {message.msgtype}.")


def start_socket_listener(sock, control_message_handler):
    thread = threading.Thread(target=_daemon_listener, args=(sock, control_message_handler), daemon=True)
    thread.start()
    return thread


def _daemon_listener(sock, control_message_handler):
    logger.info("Listener Daemon starting.")
    while True:
        try:
            msg = _read_from_socket(sock)
            if isinstance(msg, data.IGMPControl):
                logger.info(f"Control message received: {msg}")
                control_message_handler.process_control_message(msg)
            else:
                logger.warning(f"Warning, skipping packet..{msg}")
        except Exception:
            logger.exception("An error occurred in thread reading and processing multicast routing socket."
                             "  This will be ignored.")


def _ttls_list(phyints: dict[data.Interface, int], vifs_dict: dict[str, dict]) -> list[int]:
    ttls = [0] * len(vifs_dict)
    vifs = list(vifs_dict.keys())
    for inter, ttl in phyints.items():
        ttls[vifs.index(inter.name)] = ttl
    return ttls


def _read_from_socket(sock):
    buff, _ = sock.recvfrom(BUFFER_SIZE)
    return _filter_ip(kernel.parse_ip_header(buff), buff)


def _filter_ip(ip_header: data.IPHeader, buffer: bytes):
    if ip_header.protocol == data.IPProtocol.IGMP:
        return kernel.parse_igmp(buffer[ip_header.ihl * 4:])
    if ip_header.protocol == data.IPProtocol.CONTROL:
        return kernel.parse_igmp_control(buffer)
    logger.warning("warning, skipping packet...")


def _group_matches(route_group: IPv4Address | IPv4Network, packet_group: IPv4Address) -> bool:
    if isinstance(route_group, (ipaddress.IPv4Network,)):
        return packet_group in route_group
    return str(route_group) == str(packet_group)


def _mroute_from_payload(payload: dict) -> MRoute:
    """Parse a JSON payload into an MRoute.

    Expected keys:
    - from: incoming interface name (or from_)
    - group: multicast group (e.g. "239.1.0.1" or "239.1.0.0/24")
    - to: outgoing map (either a dict {"br0": 1} or a string "br0=1,eth1=1")
    - source: optional source (default "0.0.0.0")
    """
    from_ = payload.get("from", payload.get("from_"))
    if not from_:
        raise ValueError("mroute missing 'from'")

    group_raw = payload.get("group")
    if not group_raw:
        raise ValueError("mroute missing 'group'")

    group_s = str(group_raw).strip()
    if "/" in group_s:
        grp = ipaddress.ip_network(group_s, strict=False)
        if not isinstance(grp, ipaddress.IPv4Network):
            raise ValueError("only IPv4 multicast is supported")
        group_obj: IPv4Address | IPv4Network = grp
    else:
        grp = ipaddress.ip_address(group_s)
        if not isinstance(grp, ipaddress.IPv4Address):
            raise ValueError("only IPv4 multicast is supported")
        group_obj = grp

    to_raw = payload.get("to", {})
    if isinstance(to_raw, str):
        to: dict[str, int] = {}
        for part in [p.strip() for p in to_raw.split(",") if p.strip()]:
            if "=" in part:
                k, v = part.split("=", 1)
                to[k.strip()] = int(v.strip() or "1")
            else:
                to[part] = 1
    elif isinstance(to_raw, dict):
        to = {str(k): int(v) for k, v in to_raw.items()}
    else:
        raise ValueError("mroute 'to' must be a dict or string")

    source_raw = payload.get("source", ANY_ADDR)
    src = ipaddress.ip_address(str(source_raw))
    if not isinstance(src, ipaddress.IPv4Address):
        raise ValueError("only IPv4 multicast is supported")

    return MRoute(from_=str(from_), group=group_obj, to=to, source=src)
