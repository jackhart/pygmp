"""Implementation of a static multicast routing daemon.

    Provides a REST API for managing multicast routing, with support for:
    - Static routes (source-specific multicast with explicit source addresses)
    - Dynamic/wildcard routes (any-source multicast, matched on-demand by the kernel)
    - CIDR prefix matching for multicast groups

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

from ipaddress import IPv4Address
import threading
from fastapi import HTTPException
from pygmp.daemons.utils import get_logger
from pygmp.daemons.config import load_config, MRoute
from pygmp import kernel, data


logger = get_logger(__name__)

ANY_ADDR = "0.0.0.0"
BUFFER_SIZE = 6000


def main(sock, args, app):
    """Initialize and start the simple multicast routing daemon.

    This is the main entry point called from ``__main__.py``. It:
    1. Loads the configuration file
    2. Initializes the kernel multicast routing table
    3. Registers configured VIFs and static/dynamic routes
    4. Starts the background socket listener for kernel control messages
    5. Sets up REST API endpoints on the FastAPI app

    Args:
        sock: The IGMP raw socket (from ``kernel.igmp_socket()``).
        args: Parsed CLI arguments (must include ``args.config``).
        app: A FastAPI application instance.

    Returns:
        The FastAPI app with all routes registered.
    """
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
    """Register all REST API route handlers on the FastAPI app.

    Endpoints:
        GET  /vifs                    - List all virtual interfaces
        GET  /vifs/{interface_name}   - Get a specific VIF by name
        GET  /static_mfc             - List all static multicast routes
        GET  /static_mfc/{vif_index} - List static routes for a VIF
        GET  /dynamic_mfc            - List all dynamic/wildcard routes
        GET  /dynamic_mfc/{vif_index}- List dynamic routes for a VIF
        POST /vifs                   - Add a new virtual interface
        POST /mfc                    - Add a multicast route
        DELETE /vifs/{interface_name} - Remove a virtual interface
        DELETE /mfc                   - Remove a multicast route

    Args:
        app: FastAPI application instance.
        vif_manager: VifManager instance.
        mfc_manager: MfcManager instance.
        control_msg_handler: ControlMessageHandler instance.

    Returns:
        The app with routes registered.
    """

    @app.get("/vifs")
    def vifs():
        """List all registered virtual multicast interfaces."""
        return vif_manager.vifs()

    @app.get("/vifs/{interface_name}")
    def vifs_by_name(interface_name: str):
        """Get a specific virtual interface by name."""
        try:
            return vif_manager.vifs()[interface_name]
        except KeyError:
            raise HTTPException(status_code=404,
                                detail=f"Interface '{interface_name}' not found")

    @app.get("/static_mfc")
    def static_mfc():
        """List all static (source-specific) multicast forwarding cache entries."""
        return mfc_manager.static_mfc()

    @app.get("/static_mfc/{vif_index}")
    def static_mfc_by_vifi(vif_index: int):
        """List static multicast routes for a specific incoming VIF index."""
        result = mfc_manager.static_mfc()
        if vif_index not in result:
            raise HTTPException(status_code=404,
                                detail=f"No static routes for VIF index {vif_index}")
        return result[vif_index]

    @app.get("/dynamic_mfc")
    def dynamic_mfc():
        """List all dynamic (any-source/wildcard) multicast route rules."""
        return mfc_manager.dynamic_mfc()

    @app.get("/dynamic_mfc/{vif_index}")
    def dynamic_mfc_by_vifi(vif_index: int):
        """List dynamic multicast routes for a specific incoming VIF index."""
        result = mfc_manager.dynamic_mfc()
        if vif_index not in result:
            raise HTTPException(status_code=404,
                                detail=f"No dynamic routes for VIF index {vif_index}")
        return result[vif_index]

    @app.post("/vifs")
    def add_vif(interface_address_or_index: IPv4Address | int, mcast_index: int | None = None):
        """Add a new virtual multicast interface.

        The interface can be identified by its IPv4 address or system interface index.
        """
        interfaces = kernel.network_interfaces()
        if isinstance(interface_address_or_index, IPv4Address):
            match = next((interface for interface in interfaces.values()
                          if str(interface_address_or_index) in interface.addresses), None)
            if not match:
                raise HTTPException(status_code=404,
                                    detail=f"No interface with address {interface_address_or_index}")
        else:
            match = next((interface for interface in interfaces.values()
                          if interface.index == interface_address_or_index), None)
            if not match:
                raise HTTPException(status_code=404,
                                    detail=f"No interface with index {interface_address_or_index}")

        try:
            vif_manager.add(match, mcast_index)
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))
        return vif_manager.vifs()[match.name]

    @app.delete("/vifs/{interface_name}")
    def delete_vif(interface_name: str):
        """Remove a virtual interface by name."""
        try:
            vif_manager.remove_by_name(interface_name)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    @app.post("/mfc")
    def add_mfc(mroute: MRoute):
        """Add a multicast forwarding route.

        If ``source`` is ``0.0.0.0``, the route is treated as a dynamic/wildcard rule
        that will be applied when the kernel reports unmatched multicast traffic.
        Otherwise, the route is installed directly into the kernel's MFC table.
        """
        try:
            mfc_manager.add(mroute)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {"status": "ok"}

    @app.delete("/mfc")
    def delete_mfc(mroute: MRoute):
        """Remove a multicast forwarding route."""
        try:
            mfc_manager.remove(mroute)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        return {"status": "ok"}

    return app


class VifManager:
    """Manages Virtual Interfaces (VIFs) in the kernel multicast routing table.

    VIFs map physical (or virtual) network interfaces to multicast routing indices
    used by the kernel's MFC entries.

    Args:
        sock: IGMP raw socket.
        phyint: Optional list of interfaces to register on initialization.
    """

    def __init__(self, sock: kernel.InetRawSocketType, phyint: list[data.Interface] | None = None):
        self.sock = sock
        self._vif_name_list = list(self.vifs().keys())
        if phyint:
            for i, interf in enumerate(phyint):
                self.add(interf, i)

    def vifs(self) -> dict[str, data.VIFTableEntry]:
        """Returns a dictionary of the virtual multicast interfaces registered in the kernel.

        Returns:
            Dictionary mapping interface names to VIFTableEntry objects.
        """
        vif_table = {entry.name: entry for entry in kernel.ip_mr_vif()}
        return vif_table

    def vifi(self, name) -> int:
        """Returns the multicast VIF index for the given interface.

        Args:
            name: Interface name.

        Returns:
            The VIF index.

        Raises:
            ValueError: If the interface is not registered as a VIF.
        """
        try:
            return self._vif_name_list.index(name)
        except ValueError as e:
            raise ValueError(f"Could not find VIF index for interface '{name}'.") from e

    def add(self, interf: data.Interface, mcast_index: int | None = None):
        """Adds a virtual multicast interface to the kernel.

        Args:
            interf: The network interface to register.
            mcast_index: Optional explicit VIF index. If None, the next available index is used.

        Raises:
            ValueError: If the interface is already registered.
        """
        if mcast_index is None:
            vifs = self.vifs()
            if interf.name in vifs:
                raise ValueError(f"Interface '{interf.name}' already exists as a VIF.")
            mcast_index = len(vifs)
        kernel.add_vif(self.sock, data.VifCtl(vifi=mcast_index, lcl_addr=int(interf.index)))
        self._vif_name_list = list(self.vifs().keys())

    def remove_by_index(self, mc_index: int):
        """Removes a virtual multicast interface from the kernel by multicast index.

        Args:
            mc_index: The VIF index to remove.
        """
        vifctl = data.VifCtl(vifi=mc_index, lcl_addr=ANY_ADDR)
        kernel.del_vif(self.sock, vifctl)
        self._vif_name_list = list(self.vifs().keys())

    def remove_by_name(self, interface_name: str):
        """Removes a virtual multicast interface from the kernel by name.

        Args:
            interface_name: Name of the interface to remove.

        Raises:
            ValueError: If the interface is not registered as a VIF.
        """
        try:
            vif_entry = self.vifs()[interface_name]
        except KeyError as e:
            raise ValueError(f"Interface '{interface_name}' does not exist as a VIF.") from e
        kernel.del_vif(self.sock, data.VifCtl(vifi=vif_entry.index, lcl_addr=vif_entry.local_addr_or_interface))
        self._vif_name_list = list(self.vifs().keys())

    def make_ttls_list(self, phyints: dict[str | int, int]) -> list[int]:
        """Build a TTL forwarding list for use in MFC entries.

        The list has one entry per registered VIF. Non-zero values indicate that
        packets should be forwarded out that VIF if the packet TTL meets or exceeds
        the threshold.

        Args:
            phyints: Dictionary mapping interface names (or VIF indices) to TTL thresholds.

        Returns:
            List of TTL thresholds indexed by VIF index.

        Raises:
            ValueError: If an interface name or index is not found.
        """
        ttls = [0] * len(self._vif_name_list)
        for inter, ttl in phyints.items():
            if isinstance(inter, str):
                inter = self.vifi(inter)
            try:
                ttls[inter] = ttl
            except IndexError as e:
                raise ValueError(f"VIF index {inter} does not exist.") from e
        return ttls


class MfcManager:
    """Manages the Multicast Forwarding Cache (MFC).

    Handles two types of routes:
    - **Static routes** (source != 0.0.0.0): Installed directly into the kernel MFC table.
      These forward multicast from a specific source to configured outgoing interfaces.
    - **Dynamic routes** (source == 0.0.0.0): Stored in-memory as wildcard rules. When the
      kernel sends an ``IGMPMSG_NOCACHE`` control message (unmatched multicast packet),
      the daemon matches it against dynamic rules and installs a temporary MFC entry.

    Args:
        sock: IGMP raw socket.
        vif_manager: VifManager instance for interface index lookups.
        mroute_list: Optional list of routes to install on initialization.
    """

    def __init__(self, sock, vif_manager, mroute_list: list[MRoute] | None = None):
        self.sock = sock
        self.vif_manager = vif_manager
        self._dynamic_mroutes: dict[int, list[MRoute]] = {}
        if mroute_list:
            for mroute in mroute_list:
                self.add(mroute)

    def static_mfc(self) -> dict[int, list[data.MFCEntry]]:
        """Returns static MFC entries from the kernel, grouped by incoming VIF index.

        Returns:
            Dictionary mapping VIF indices to lists of MFCEntry objects.
        """
        result = {}
        for entry in kernel.ip_mr_cache():
            if entry.iif in result:
                result[entry.iif].append(entry)
            else:
                result[entry.iif] = [entry]
        return result

    def dynamic_mfc(self) -> dict[int, list[MRoute]]:
        """Returns in-memory dynamic/wildcard route rules, grouped by incoming VIF index.

        Returns:
            Dictionary mapping VIF indices to lists of MRoute objects.
        """
        return self._dynamic_mroutes

    def add(self, mroute: MRoute):
        """Add a multicast route.

        Routes with source == 0.0.0.0 are stored as dynamic rules.
        Routes with a specific source are installed into the kernel MFC.

        Args:
            mroute: The multicast route to add.
        """
        if str(mroute.source) == ANY_ADDR:
            vifi = self.vif_manager.vifi(mroute.from_)
            if vifi in self._dynamic_mroutes:
                # Check if a route for the same group already exists and update it
                for i, existing in enumerate(self._dynamic_mroutes[vifi]):
                    if existing.group == mroute.group:
                        self._dynamic_mroutes[vifi][i] = mroute
                        return
                self._dynamic_mroutes[vifi].append(mroute)
            else:
                self._dynamic_mroutes[vifi] = [mroute]
        else:
            self._add_mfc_syscall(mroute)

    def remove(self, mroute: MRoute):
        """Remove a multicast route.

        Args:
            mroute: The route to remove.

        Raises:
            ValueError: If the route does not exist.
        """
        parent = self.vif_manager.vifi(mroute.from_)
        if str(mroute.source) == ANY_ADDR:
            if parent in self._dynamic_mroutes:
                for i, existing in enumerate(self._dynamic_mroutes[parent]):
                    if existing.group == mroute.group:
                        self._dynamic_mroutes[parent].pop(i)
                        if not self._dynamic_mroutes[parent]:
                            del self._dynamic_mroutes[parent]
                        return
            raise ValueError(f"Dynamic route for group {mroute.group} on VIF {parent} does not exist.")
        else:
            kernel.del_mfc(self.sock, data.MfcCtl(origin=mroute.source, mcastgroup=mroute.group, parent=parent, ttls=[]))

    def match(self, vifi: int, group, source_address=ANY_ADDR) -> MRoute | None:
        """Find a matching route for an incoming multicast packet.

        For dynamic routes (source_address == 0.0.0.0), checks all dynamic rules on
        the given VIF for a group match (supports both exact and CIDR prefix matching).

        For static routes, searches the kernel MFC for an exact source+group match.

        Args:
            vifi: Incoming VIF index.
            group: Multicast group address of the packet.
            source_address: Source IP of the packet (default: any).

        Returns:
            Matching MRoute (for dynamic) or MFCEntry (for static), or None.
        """
        try:
            if str(source_address) == ANY_ADDR:
                return next(
                    (route for route in self._dynamic_mroutes.get(vifi, [])
                     if route.matches_group(group)),
                    None)
            # For static routes, check kernel MFC table
            return next(
                (entry for entry in self.static_mfc().get(vifi, [])
                 if str(entry.group) == str(group) and str(entry.origin) == str(source_address)),
                None)
        except KeyError:
            return None

    def _add_mfc_syscall(self, mroute: MRoute):
        """Install a static MFC entry into the kernel.

        Args:
            mroute: The route to install.
        """
        mfcctl = data.MfcCtl(origin=mroute.source,
                             mcastgroup=mroute.group,
                             parent=self.vif_manager.vifi(mroute.from_),
                             ttls=self.vif_manager.make_ttls_list(mroute.to))
        kernel.add_mfc(self.sock, mfcctl)


class ControlMessageHandler:
    """Processes kernel control messages from the IGMP socket.

    When the kernel encounters a multicast packet with no matching MFC entry,
    it sends an ``IGMPMSG_NOCACHE`` control message. This handler looks up matching
    dynamic route rules and installs a temporary MFC entry to handle the traffic.

    Args:
        sock: IGMP raw socket.
        mfc_manager: MfcManager for route lookups.
        vif_manager: VifManager for TTL list generation.
    """

    def __init__(self, sock, mfc_manager: MfcManager, vif_manager: VifManager):
        self.sock = sock
        self.mfc_manager = mfc_manager
        self.vif_manager = vif_manager

    def process_control_message(self, message: data.IGMPControl):
        """Handle a kernel control message.

        For ``IGMPMSG_NOCACHE``: looks up a matching dynamic route and installs
        an MFC entry for the specific source+group+VIF combination.

        Args:
            message: The kernel control message.

        Raises:
            ValueError: If the control message type is unrecognized.
        """
        if message.msgtype == data.ControlMsgType.IGMPMSG_NOCACHE:
            match = self.mfc_manager.match(message.vif, message.im_dst, message.im_src)
            if match:
                if isinstance(match, MRoute):
                    # Dynamic route match: install MFC entry using the route's outgoing map
                    ttls_list = self.vif_manager.make_ttls_list(match.to)
                else:
                    # Static MFCEntry match: use its existing OIF map
                    ttls_list = self.vif_manager.make_ttls_list(match.oifs)
                mfctl = data.MfcCtl(origin=message.im_src, mcastgroup=message.im_dst,
                                    parent=message.vif, ttls=ttls_list)
                kernel.add_mfc(self.sock, mfctl)
            else:
                logger.debug(f"No matching route for NOCACHE: vif={message.vif} "
                             f"src={message.im_src} dst={message.im_dst}")
        elif message.msgtype == data.ControlMsgType.IGMPMSG_WRONGVIF:
            logger.warning(f"WRONGVIF: packet on vif={message.vif} "
                           f"src={message.im_src} dst={message.im_dst}")
        else:
            logger.warning(f"Unhandled control message type: {message.msgtype}")


def start_socket_listener(sock, control_message_handler):
    """Start a background thread that reads from the IGMP socket.

    The listener thread continuously reads packets and control messages from the
    kernel and dispatches them to the control message handler.

    Args:
        sock: IGMP raw socket.
        control_message_handler: Handler for kernel control messages.

    Returns:
        The started daemon thread.
    """
    thread = threading.Thread(target=_daemon_listener, args=(sock, control_message_handler), daemon=True)
    thread.start()
    return thread


def _daemon_listener(sock, control_message_handler):
    """Background listener loop for the IGMP socket.

    Reads packets, identifies control messages vs IGMP messages, and dispatches
    accordingly. Errors are logged but do not stop the listener.
    """
    logger.info("Listener daemon starting.")
    while True:
        try:
            msg = _read_from_socket(sock)
            if isinstance(msg, data.IGMPControl):
                logger.info(f"Control message received: {msg}")
                control_message_handler.process_control_message(msg)
            else:
                logger.debug(f"IGMP message received (skipping): {msg}")
        except Exception:
            logger.exception("Error in socket listener thread. Continuing.")


def _read_from_socket(sock):
    """Read and parse a single message from the IGMP socket.

    Returns:
        Parsed IGMPControl, IGMP, IGMPv3Query, or IGMPv3MembershipReport.
    """
    buff, _ = sock.recvfrom(BUFFER_SIZE)
    return _filter_ip(kernel.parse_ip_header(buff), buff)


def _filter_ip(ip_header: data.IPHeader, buffer: bytes):
    """Dispatch parsing based on IP protocol type.

    Args:
        ip_header: Parsed IP header.
        buffer: Raw packet buffer.

    Returns:
        Parsed message object appropriate to the protocol.
    """
    if ip_header.protocol == data.IPProtocol.IGMP:
        return kernel.parse_igmp(buffer[ip_header.ihl * 4:])
    if ip_header.protocol == data.IPProtocol.CONTROL:
        return kernel.parse_igmp_control(buffer)
    logger.warning(f"Unknown IP protocol {ip_header.protocol}, skipping packet.")
