"""
TODO:
    Investigate syscalls that are not yet implemented.
        - MRT_TABLE -- Linux only, support for multiple MRT tables.  (e.g,, for multiple routing daemons)
        - MRT_ADD_MFC_PROXY
        - MRT_DEL_MFC_PROXY
        - SIOCGETRPF  -- Get the RPF neighbor for a given source and group?
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
import struct
from contextlib import contextmanager
from typing import TypeVar
import socket
import fcntl
from ipaddress import ip_address, IPv4Address, IPv6Address

from pygmp.data import VifReq, IpMreq, VifCtl, MfcCtl, SGReq, IPHeader, \
    IGMPControl, Interface, VIFTableEntry, MFCEntry, \
    IGMP, IGMPType, IGMPv3Query, IGMPv3MembershipReport
from pygmp import _kernel


# This naming is used to distinguish socket types between methods.
InetRawSocketType = TypeVar("InetRawSocketType", bound=socket.socket)  # FIXME - no good way to type a raw socket
InetAnySocket = TypeVar("InetAnySocket", bound=socket.socket)


@contextmanager
def igmp_socket() -> InetRawSocketType:
    """The IGMP socket. A raw socket used to communicate wither kernel multicast routing code."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_IGMP)
    yield sock
    sock.close()


def mrt_version(sock: InetRawSocketType) -> str:
    """Get the version of the kernel mroute."""
    return hex(sock.getsockopt(socket.IPPROTO_IP, _kernel.MRT_VERSION))


def enable_mrt(sock: InetRawSocketType) -> None:
    """Enable the kernel multicast routing socket to receive control messages."""
    try:
        sock.setsockopt(socket.IPPROTO_IP, _kernel.MRT_INIT, 1)
    except OSError as e:
        if e.errno == 98:
            # "Address already in use"
            raise OSError("The MRT socket is already enabled.")
        raise


def disable_mrt(sock: InetRawSocketType) -> None:
    """Disable the kernel multicast routing socket to no longer receive control messages.

        Ubuntu docs say setting MRT_INIT to 0 disabled it.
            https://manpages.ubuntu.com/manpages/xenial/en/man4/multicast.4freebsd.html
        Linux source code tells a different story.
            https://github.com/torvalds/linux/blob/master/net/ipv4/ipmr.c#L1411
    """
    try:
        sock.setsockopt(socket.IPPROTO_IP, _kernel.MRT_DONE, 1)
    except PermissionError as e:
        if e.errno == 13:
            raise OSError("The MRT socket is already disabled.")
        raise


def enable_pim(sock: InetRawSocketType) -> None:
    """Enable PIM code & PIM assert mode in the kernel.

        FIXME - the distinction between PIM and PIM assert mode is not clear.
            - If PIM is disabled and you enable assert, PIM will be enabled.
            - If PIM assert is disabled, you cannot enable PIM.
    """
    sock.setsockopt(socket.IPPROTO_IP, _kernel.MRT_PIM, 1)
    sock.setsockopt(socket.IPPROTO_IP, _kernel.MRT_ASSERT, 1)


def disable_pim(sock: InetRawSocketType) -> None:
    """Disable PIM code & PIM assert mode in the kernel.

        FIXME - the distinction between PIM and PIM assert mode is not clear.
            - If PIM is disabled and you enable assert, PIM will be enabled.
            - If PIM assert is disabled, you cannot enable PIM.
    """
    sock.setsockopt(socket.IPPROTO_IP, _kernel.MRT_PIM, 0)
    sock.setsockopt(socket.IPPROTO_IP, _kernel.MRT_ASSERT, 0)


def pim_is_enabled(sock: InetRawSocketType) -> bool:
    """Check if PIM code & PIM assert mode is enabled in the kernel."""
    return bool(sock.getsockopt(socket.IPPROTO_IP, _kernel.MRT_PIM)) \
           and bool(sock.getsockopt(socket.IPPROTO_IP, _kernel.MRT_ASSERT))


def add_vif(sock: InetRawSocketType, vifctl: VifCtl) -> None:
    """Add a multicast VIF to the kernel multicast routing table.

        :parameter sock: The IGMP socket.
        :parameter vifctl: Metadata to create the new VIF.
    """
    _kernel.add_vif(sock, vifctl.vifi, vifctl.threshold, vifctl.rate_limit, str(vifctl.lcl_addr), str(vifctl.rmt_addr))


def del_vif(sock: InetRawSocketType, vifctl: VifCtl) -> None:
    """Delete a multicast VIF from the kernel multicast routing table."""
    _kernel.del_vif(sock, vifctl.vifi)


def get_vif_counts(sock: InetRawSocketType, vif_req: VifReq) -> VifReq:
    """Get packet and byte counts for a VIF in the multicast routing table."""
    sioc_vif_req = struct.pack(vif_req.format, vif_req.vifi, vif_req.icount, vif_req.ocount, vif_req.ibytes, vif_req.obytes)
    sioc_vif_result = fcntl.ioctl(sock.fileno(), _kernel.SIOCGETVIFCNT, sioc_vif_req, True)
    return VifReq(*struct.unpack(VifReq.format, sioc_vif_result))


def get_mfc_counts(sock: InetRawSocketType, sg_req: SGReq) -> SGReq:
    """Get packet and byte counts for a source-group mfc entry."""
    sioc_sg_req = struct.pack(sg_req.format, sg_req.src.packed, sg_req.grp.packed, sg_req.pktcnt, sg_req.bytecnt, sg_req.wrong_if)
    sioc_sg_result = fcntl.ioctl(sock.fileno(), _kernel.SIOCGETSGCNT, sioc_sg_req, True)
    unpacked_args = list(struct.unpack(SGReq.format, sioc_sg_result))
    unpacked_args[0], unpacked_args[1] = ip_address(unpacked_args[0]), ip_address(unpacked_args[1])
    return SGReq(*unpacked_args)


def add_mfc(sock: InetRawSocketType, mfcctl: MfcCtl) -> None:
    """Add a multicast forwarding cache entry to the kernel multicast routing table.
        TODO - support expire field.
    """
    _kernel.add_mfc(sock, str(mfcctl.origin), str(mfcctl.mcastgroup), mfcctl.parent, mfcctl.ttls)


def del_mfc(sock: InetRawSocketType, mfcctl: MfcCtl) -> None:
    """Delete a multicast forwarding cache entry from the kernel multicast routing table."""
    _kernel.del_mfc(sock, str(mfcctl.origin), str(mfcctl.mcastgroup), mfcctl.parent)


def flush(sock: InetRawSocketType, vifs=True, mfc=True, static=True) -> None:
    """Flush data in the kernel multicast routing table.
        TODO - it is not clear to me how/when static VIFs and MFCs are created.
    """
    vifs_mask = vifs * (_kernel.MRT_FLUSH_VIFS | (static * _kernel.MRT_FLUSH_VIFS_STATIC))
    mfc_mask = mfc * (_kernel.MRT_FLUSH_MFC | (static * _kernel.MRT_FLUSH_MFC_STATIC))
    sock.setsockopt(socket.IPPROTO_IP, _kernel.MRT_FLUSH, vifs_mask | mfc_mask)


def add_membership(sock: InetAnySocket, ip_mreq: IpMreq) -> None:
    """add membership <ip_mreq>

        Runs setsockopt with IP_ADD_MEMBERSHIP option on the socket used for multicast routing.  This tells the kernel
        to join a multicast group on the specified interface.  The kernel sends an IGMP message to join the group
        initially, and then it periodically sends IGMP membership reports to maintain the membership.  When the socket
        is closed, the kernel will send an IGMP message to leave the group.

        This should not be necessary to do any multicast routing.  However, if your switch is configured with
        IGMP-snooping, sometimes IGMP messages are not properly forwarded to the router.
    """
    mreq_buff = struct.pack(ip_mreq.format, ip_mreq.multiaddr.packed, ip_mreq.interface.packed)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq_buff)


def drop_membership(sock: InetAnySocket, ip_mreq: IpMreq) -> None:
    """drop membership.

        Runs setsockopt with IP_DROP_MEMBERSHIP option on the socket used for multicast routing.  This tells the kernel
        to send an IGMP message to leave the specified group.
    """
    mreq_buff = struct.pack(ip_mreq.format, ip_mreq.multiaddr.packed, ip_mreq.interface.packed)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, mreq_buff)


def ttl(sock: InetAnySocket) -> int:
    return sock.getsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL)


def loop(sock: InetAnySocket) -> bool:
    return bool(sock.getsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP))


def interface(sock: InetAnySocket) -> str:
    in_buff = sock.getsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, 4)
    return socket.inet_ntoa(in_buff)


def parse_ip_header(buffer: bytes) -> IPHeader:
    return IPHeader(**_kernel.parse_ip_header(buffer))


def parse_igmp(buffer: bytes) -> IGMP | IGMPv3MembershipReport | IGMPv3Query:
    result_dict = _kernel.parse_igmp(buffer)
    msg_type = IGMPType(result_dict["type"])
    if msg_type == IGMPType.V3_MEMBERSHIP_REPORT:
        return IGMPv3MembershipReport(**result_dict)
    if msg_type == IGMPType.MEMBERSHIP_QUERY and len(result_dict) > 4:
        return IGMPv3Query(**result_dict)
    return IGMP(**result_dict)


def parse_igmp_control(buffer: bytes) -> IGMPControl:
    return IGMPControl(**_kernel.parse_igmp_control(buffer))


def network_interfaces() -> dict[str, Interface]:
    """Get list of VIFs from kernel.  Returns the name, IP address, and if multicast is enabled."""
    interfaces = dict()
    for inf in _kernel.network_interfaces():
        if inf["name"] not in interfaces:
            interfaces[inf["name"]] = Interface(inf["name"], inf["index"], inf["flags"])
        if inf["address"]:  # TODO - any case where flags are different but name is the same?
            interfaces[inf["name"]].addresses.append(inf["address"])

    return interfaces


def ip_mr_vif() -> list[VIFTableEntry]:
    """Parse the /proc/net/ip_mr_vif file.  Linux specific, holds the IPv4 virtual interfaces used by the active multicast routing daemon.

        Virtual file generated by the kernel code here: https://github.com/torvalds/linux/blob/master/net/ipv4/ipmr.c#L2922
            interface bytesin pktsin bytesout pktsout flags local remote
            %2td %-10s %8ld %7ld  %8ld %7ld %05X %08X %08X

        Raises FileNotFoundError if the file does not exist.

        FIXME - local_address will be index if MRT_ADD_VIF is called with one.  Currently, it is converted to an IP address.

    """
    vifs = []
    with open('/proc/net/ip_mr_vif', 'r') as f:
        next(f) # skip header line
        for line in f:
            fields = line.split()
            index, iface = int(fields[0]), fields[1]
            byin, pin, byout, pout, flags = int(fields[2]), int(fields[3]), int(fields[4]), int(fields[5]), int(fields[6])
            local, remote = host_hex_to_ip(fields[7]), host_hex_to_ip(fields[8])
            vifs.append(VIFTableEntry(index, iface, byin, pin, byout, pout, flags, local, remote))

    return vifs


def ip_mr_cache() -> list[MFCEntry]:
    """Parse the /proc/net/ip_mr_cache file.  Linux specific, holds the multicast routing cache.

        Virtual file generated by the kernel code here: https://github.com/torvalds/linux/blob/master/net/ipv4/ipmr.c#L2966
            group origin iif pkts bytes wrong [oifs]
            %08X %08X %-3hd %8lu %8lu %8lu [[%2d:%-3d] [%2d:%-3d] ...] or [ %2d:%-3d]

        Raises FileNotFoundError if the file does not exist.

    """
    with open('/proc/net/ip_mr_cache', 'r') as f:
        next(f) # skip header line
        entries = []
        for line in f:
            fields = line.strip().split()

            if len(fields) < 6 :
                raise ValueError("Encountered malformed line in /proc/net/ip_mr_cache: " + line)

            oifs = _parse_index_ttl(fields[6:]) if len(fields) > 6 else dict()
            group, origin = host_hex_to_ip(fields[0]), host_hex_to_ip(fields[1])
            entries.append(MFCEntry(group, origin, int(fields[2]), int(fields[3]), int(fields[4]), int(fields[5]), oifs))
    return entries


def host_hex_to_ip(hex_val: str) -> IPv4Address | IPv6Address:
    """Convert a hex string to an IP address.

        IP addresses are typically represented in network byte order (big-endian),
        whereas the host byte order can be little-endian depending on the architecture.

        TODO - system dependent... Not sure if we always need to reverse the bytes?
    """
    host_order = bytearray.fromhex(hex_val)
    host_order.reverse()
    big_endian = bytes(host_order)
    return ip_address(big_endian)


def _parse_index_ttl(pairs_list: list[str]) -> dict[int, int]:
    """Parse a list of index:ttl pairs into a dictionary."""
    return {int(pair.split(':')[0]): int(pair.split(':')[1]) for pair in pairs_list}
