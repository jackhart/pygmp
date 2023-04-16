"""

TODO:
    Investigate syscalls that are not yet implemented.
        - MRT_TABLE -- Linux only, support for multiple MRT tables.  (e.g,, for multiple routing daemons)
        - MRT_ADD_MFC_PROXY
        - MRT_DEL_MFC_PROXY
        - SIOCGETRPF  -- Get the RPF neighbor for a given source and group?  

"""
import struct
from contextlib import contextmanager
from ipaddress import ip_address
from typing import TypeVar
import socket
import fcntl

from pygmp.kernel.data import VifReq, IpMreq, VifCtl, MfcCtl, SGReq
from pygmp.kernel import _kernel


# This naming is used to distinguish socket types between methods.
#  FIXME - these type categorizations alone are meaningless.
InetRawSocketType = TypeVar("InetRawSocketType", bound=socket.socket)
InetAnySocket = TypeVar("InetAnySocket", bound=socket.socket)  # can any socket type (not just raw)


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
    """Add a multicast VIF to the kernel multicast routing table."""
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
    """Send an IGMP packet request."""
    mreq_buff = struct.pack(ip_mreq.format, ip_mreq.multiaddr.packed, ip_mreq.interface.packed)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq_buff)


def drop_membership(sock: InetAnySocket, ip_mreq: IpMreq) -> None:
    """Send an IGMP packet drop request."""
    mreq_buff = struct.pack(ip_mreq.format, ip_mreq.multiaddr.packed, ip_mreq.interface.packed)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, mreq_buff)


def ttl(sock: InetAnySocket) -> int:
    return sock.getsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL)


def loop(sock: InetAnySocket) -> bool:
    return bool(sock.getsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP))


def interface(sock: InetAnySocket) -> str:
    in_buff = sock.getsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, 4)
    return socket.inet_ntoa(in_buff)
