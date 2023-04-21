"""Common data structures.  These include dataclass wrappers around C structs and IP packets."""
from __future__ import annotations  # relevant to PEP 563 (postponed evaluation of annotations)
from enum import IntEnum, Enum, EnumMeta
from dataclasses import dataclass, fields
from ipaddress import ip_address, IPv4Address, IPv6Address
from typing import get_args

from pygmp import _kernel


@dataclass
class Base:
    """"Base dataclass for all other dataclasses"""
    def __post_init__(self):
        for field in fields(self):
            if isinstance(_get_type(field.type), EnumMeta):
                setattr(self, field.name, _get_type(field.type)(getattr(self, field.name)))
            elif IPv4Address in set(get_args(_get_type(field.type))):
                if not isinstance(getattr(self, field.name), str):
                    continue
                setattr(self, field.name, ip_address(getattr(self, field.name)))


class IPVersion(Enum):
    IPv4 = 4
    IPv6 = 6


class IPProtocol(Enum):
    """Protocol numbers"""
    CONTROL = 0
    IGMP = 2
    PIM = 103


class IGMPType(Enum):
    """IGMP message types"""
    MEMBERSHIP_QUERY = 0x11  # Membership query
    V1_MEMBERSHIP_REPORT = 0x12  # Version 1 membership report
    V2_MEMBERSHIP_REPORT = 0x16  # Version 2 membership report
    V2_LEAVE_GROUP = 0x17  # Leave group
    V3_MEMBERSHIP_REPORT = 0x22  # Version 3 membership report



class ControlMsgType(IntEnum):
    IGMPMSG_NOCACHE = _kernel.IGMPMSG_NOCACHE
    IGMPMSG_WRONGVIF = _kernel.IGMPMSG_WRVIFWHOLE
    IGMPMSG_WHOLEPKT = _kernel.IGMPMSG_WHOLEPKT


class InterfaceFlags(IntEnum):
    UP = 1 << 0
    BROADCAST = 1 << 1
    DEBUG = 1 << 2
    LOOPBACK = 1 << 3
    POINTOPOINT = 1 << 4
    NOTRAILERS = 1 << 5
    RUNNING = 1 << 6
    NOARP = 1 << 7
    PROMISC = 1 << 8
    ALLMULTI = 1 << 9
    MASTER = 1 << 10
    SLAVE = 1 << 11
    MULTICAST = 1 << 12
    PORTSEL = 1 << 13
    AUTOMEDIA = 1 << 14
    DYNAMIC = 1 << 15
    LOWER_UP = 1 << 16
    DORMANT = 1 << 17
    ECHO = 1 << 18

    @classmethod
    def from_value(cls, value) -> set[InterfaceFlags]:
        return set(flag for flag in cls if flag & value)


@dataclass
class IpMreq(Base):
    """Request structure for multicast socket ops.
        Linux struct: https://github.com/torvalds/linux/blob/master/include/uapi/linux/in.h#L177
    """
    format = "4s 4s"
    multiaddr: IPv4Address | IPv6Address | str  # IP multicast address of group
    interface: IPv4Address | IPv6Address | str  # local IP address of interface


@dataclass
class VifReq(Base):
    """Used in SIOCGETVIFCNT ioctl call.
        Linux struct: https://github.com/torvalds/linux/blob/master/include/uapi/linux/mroute.h#L101
    """
    format = "HLLLL"
    vifi: int  # VIF index
    icount: int = 0 # Input packet count
    ocount: int = 0  # Output packet count
    ibytes: int = 0 # Input byte count
    obytes: int  = 0 # Output byte count


@dataclass
class SGReq(Base):
    """ 'Source-Group Request' - Used in SIOCGETSGCNT ioctl call.
        Linux struct: https://github.com/torvalds/linux/blob/master/net/ipv4/ipmr.c
    """
    format = "4s 4s LLL"
    src: IPv4Address | IPv6Address | str
    grp: IPv4Address | IPv6Address | str
    pktcnt: int = 0
    bytecnt: int = 0
    wrong_if: int = 0


@dataclass
class VifCtl(Base):
    """Used in MRT_ADD_VIF and MRT_DEL_VIF
        Linux struct: https://github.com/torvalds/linux/blob/master/include/uapi/linux/mroute.h#L61
    """
    vifi: int  # VIF index
    threshold: int = 1  # TTL threshold - minimum TTL packet must have to be forwarded on vif.  Typically 1
    rate_limit: int = 0  # Rate limiter values (NI)
    lcl_addr: IPv4Address | IPv6Address | str | int = ip_address("0.0.0.0")  # Local interface address or index
    rmt_addr: IPv4Address | IPv6Address | str = ip_address("0.0.0.0")  # Remote address (NI)


@dataclass
class MfcCtl(Base):
    """Used in MRT_ADD_MFC and MRT_DEL_MFC calls.
        Linux struct: https://github.com/torvalds/linux/blob/master/include/uapi/linux/mroute.h#L80
    """
    origin: IPv4Address | IPv6Address | str  # Originating ip - used in source-specific multicast (SSM)
    mcastgroup: IPv4Address | IPv6Address | str  # Multicast address
    parent: int  # Parent vif - where packet arrived - incoming interface index
    ttls: list  # Minimum TTL thresholds for forwarding on vifs
    expire: int = 0  # time in seconds after which the cache entry will be deleted  TODO - add to method


@dataclass
class Interface(Base):
    name: str
    index: int
    flags: set[InterfaceFlags] | int
    addresses: list[str]

    def __post_init__(self):
        super().__post_init__()
        if isinstance(self.flags, int):
            self.flags = InterfaceFlags.from_value(self.flags)


@dataclass
class IGMPControl(Base):
    """The format sent from kernel over the IGMP socket.
        Linux struct: https://github.com/torvalds/linux/blob/master/include/uapi/linux/mroute.h#L112
    """
    msgtype: ControlMsgType  # control message type
    mbz: int  # Must be zero
    vif: int  # Low 8 bits of VIF number
    vif_hi: int  # High 8 bits of VIF number
    im_src: IPv4Address | IPv6Address | str   # IP address of source of packet
    im_dst: IPv4Address | IPv6Address | str   # IP address of destination of packet


@dataclass
class IPHeader(Base):
    version: IPVersion
    ihl: int
    tos: int  # Type of service
    tot_len: int  # Total length
    id: int  # Identification
    frag_off: int  # fragment offset
    ttl: int  # Time to live
    protocol: IPProtocol  # Protocol
    check: int  # Header checksum
    src_addr: IPv4Address | IPv6Address | str   # Source address
    dst_addr: IPv4Address | IPv6Address | str   # Destination address


@dataclass
class IGMP(Base):
    """The format of an IGMP message in an IP packets payload."""
    type : IGMPType  # IGMP version
    code: int
    checksum: int  # Checksum
    group: IPv4Address | IPv6Address | str  # Group address


@dataclass
class VIFTableEntry(Base):
    """The format of an entry in the VIF table at /proc/net/ip_mr_vif."""
    index: int
    interface: str
    bytes_in: int
    pkts_in: int
    bytes_out: int
    pkts_out: int
    flags: int
    local_addr: IPv4Address | IPv6Address | str
    remote_addr: IPv4Address | IPv6Address | str



@dataclass
class VifCtl(Base):
    """Used in MRT_ADD_VIF and MRT_DEL_VIF
        Linux struct: https://github.com/torvalds/linux/blob/master/include/uapi/linux/mroute.h#L61
    """
    vifi: int  # VIF index
    threshold: int = 1  # TTL threshold - minimum TTL packet must have to be forwarded on vif.  Typically 1
    rate_limit: int = 0  # Rate limiter values (NI)
    lcl_addr: IPv4Address | IPv6Address | str | int = ip_address("0.0.0.0")  # Local interface address or index
    rmt_addr: IPv4Address | IPv6Address | str = ip_address("0.0.0.0")  # Remote address (NI)



@dataclass
class MFCEntry(Base):
    """The format of an entry in the MFC table at /proc/net/ip_mr_cache."""
    group: IPv4Address | IPv6Address | str
    origin: IPv4Address | IPv6Address | str
    iif: int
    packets: int
    bytes: int
    wrong_if: int
    oifs: dict[int, int]  # outgoing_if_indx : ttl


def _get_type(type_obj: str | type) -> type:
    """Get the type from the type hint."""
    if isinstance(type_obj, type):
        return type_obj
    return eval(type_obj)


