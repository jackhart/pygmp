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
from time import sleep
import signal
import threading
from pygmp.daemons.utils import get_logger
from pygmp.daemons.config import load_config, MRoute, Config
from pygmp import kernel, data


logger = get_logger("daemon")

ANY_ADDR = "0.0.0.0"  # TODO - get constant from C extension
BUFFER_SIZE = 6000  # FIXME - think through buffer size


def main(args):
    signal.signal(signal.SIGTERM, program_cleanup)
    serve()


def serve():
    config = load_config("/home/jack/Documents/projects/pygmp/tests/simple.ini")  # TODO - reorg
    with kernel.igmp_socket() as sock:
        kernel.flush(sock)
        kernel.disable_pim(sock)
        kernel.enable_mrt(sock)

        vif_manager = VifManager(sock, config.phyint)
        mfc_manager = MfcManager(sock, vif_manager, config.mroute)
        control_msg_handler = ControlMessageHandler(sock, mfc_manager, vif_manager)

        thread = start_socket_listener(sock, control_msg_handler)
        thread.join()


def program_cleanup(signum, frame):
    # TODO - signals
    logger.info("My time has come.")
    exit(0)


class VifManager:
    def __init__(self, sock: kernel.InetRawSocketType, phyint: list[data.Interface] | None = None):
        self.sock = sock
        if phyint:
            for i, interf in enumerate(phyint):
                self.add(interf, i)

    def vifs(self):
        """Returns a dictionary of the virtual multicast interfaces registered in the kernel."""
        return {entry.interface: entry for entry in kernel.ip_mr_vif()}

    def add(self, interf: data.Interface, mcast_index: int | None = None):
        """Adds a virtual multicast interface to the kernel.
            If index is provided, it is used and the interface is not checked for existence before adding.
        """
        if not mcast_index:
            vifs = self.vifs()
            if interf.name in vifs:
                raise ValueError(f"Interface {interf.name} already exists.")
            mcast_index = len(vifs)
        kernel.add_vif(self.sock, data.VifCtl(vifi=mcast_index, lcl_addr=int(interf.index)))

    def remove_by_index(self, mc_index: int):
        """Removes a virtual multicast interface from the kernel by multicast index."""
        vifctl = data.VifCtl(vifi=mc_index, lcl_addr=ANY_ADDR)
        kernel.del_vif(self.sock, vifctl)

    def remove_by_name(self, interface_name: str):
        """Removes a virtual multicast interface from the kernel by name."""
        try:
            vif_entry = self.vifs()[interface_name]
        except KeyError:
            raise ValueError(f"Interface {interface_name} does not exist.")
        kernel.del_vif(self.sock, data.VifCtl(vifi=vif_entry.vifi, lcl_addr=vif_entry.local_addr))


class MfcManager:
    def __init__(self, sock, vif_manager, mroute_list: list[MRoute] | None = None):
        self.sock = sock
        self.vif_manager = vif_manager
        self._vif_table = self.vif_manager.vifs()
        self._vif_name_list = list(self._vif_table.keys())
        self._dynamic_mroutes = {}
        if mroute_list:
            for mroute in mroute_list:
                self.add(mroute)

    def mfc(self):
        return kernel.ip_mr_cache()

    def dynamic_mfc(self):
        return self._dynamic_mroutes

    def add(self, mroute: MRoute):
        if str(mroute.source) == ANY_ADDR:
            # FIXME - group logic is wrong.  should index by interface?
            self._dynamic_mroutes[str(mroute.group)] = mroute
        else:
            self._add_mfc_syscall(mroute)

    def remove(self, mroute: MRoute):
        try:
            parent = self._vif_name_list.index(mroute.from_.name)
        except ValueError:
            raise ValueError(f"Could not find index for Interface {mroute.from_.name}.")
        kernel.del_mfc(self.sock, data.MfcCtl(origin=mroute.source, mcastgroup=mroute.group, parent=parent, ttls=[]))

    def refresh_vifs(self):
        self._vif_table = self.vif_manager.vifs()
        self._vif_name_list = list(self._vif_table.keys())

    def _add_mfc_syscall(self, mroute: MRoute):
        mfcctl = data.MfcCtl(origin=mroute.source,
                             mcastgroup=mroute.group,
                             parent=self._vif_name_list.index(mroute.from_.name),
                             ttls=_ttls_list(mroute.to, self._vif_table))
        kernel.add_mfc(self.sock, mfcctl)


class ControlMessageHandler:
    def __init__(self, sock, mfc_manager: MfcManager, vif_manager: VifManager):
        self.sock = sock
        self.mfc_manager = mfc_manager
        self.vif_manager = vif_manager

    def process_control_message(self, route: data.IGMPControl):
        if route.msgtype == data.ControlMsgType.IGMPMSG_NOCACHE:
            if str(route.im_dst) in self.mfc_manager.dynamic_mfc():
                ttls_list = _ttls_list(self.mfc_manager.dynamic_mfc()[str(route.im_dst)].to, self.vif_manager.vifs())
                mfctl = data.MfcCtl(origin=route.im_src, mcastgroup=route.im_dst, parent=route.vif, ttls=ttls_list)
                kernel.add_mfc(self.sock, mfctl)
        else:
            logger.warning(f"{route.msgtype} is not supported.")


def start_socket_listener(sock, control_message_handler):
    thread = threading.Thread(target=_daemon_listener, args=(sock, control_message_handler), daemon=True)
    thread.start()
    return thread


def _daemon_listener(sock, control_message_handler):
    while True:
        logger.info("Listener Daemon starting.")
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


def _ttls_list(phyints: list[data.Interface], vifs_dict: dict[str, dict]) -> list[int]:
    ttls = [0] * len(vifs_dict)
    vifs = list(vifs_dict.keys())
    for inter in phyints:
        ttls[vifs.index(inter.name)] = 1  # TODO - custom ttl for each phyint
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
