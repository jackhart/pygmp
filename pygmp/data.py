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

from __future__ import annotations  # relevant to PEP 563 (postponed evaluation of annotations)

import ipaddress
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
    """IP Protocol numbers"""
    CONTROL = 0
    IGMP = 2
    PIM = 103


class IGMPv3RecordType(Enum):
    MODE_IS_INCLUDE = 1
    MODE_IS_EXCLUDE = 2
    CHANGE_TO_INCLUDE_MODE = 3
    CHANGE_TO_EXCLUDE_MODE = 4
    ALLOW_NEW_SOURCES = 5
    BLOCK_OLD_SOURCES = 6


class IGMPType(Enum):
    """IGMP message types"""
    MEMBERSHIP_QUERY = 0x11  # Membership query
    V1_MEMBERSHIP_REPORT = 0x12  # Version 1 membership report
    V2_MEMBERSHIP_REPORT = 0x16  # Version 2 membership report
    V2_LEAVE_GROUP = 0x17  # Version 2 Leave group
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
    max_response_time: int
    checksum: int  # Checksum
    group: IPv4Address | str  # Group address


@dataclass
class IGMPv3MembershipReport(Base):
    """ """
    type: IGMPType
    checksum: int
    num_records: int
    grec_list: list[IGMPv3Record | dict]

    def __post_init__(self):
        super().__post_init__()
        self.grec_list = [IGMPv3Record(**grec) for grec in self.grec_list if isinstance(grec, dict)]


@dataclass
class IGMPv3Record(Base):
    """ """
    type: IGMPv3RecordType
    auxwords: int
    nsrcs: int
    mca: IPv4Address | str
    src_list: list[IPv4Address | str]  # FIXME / TODO - IPv4Address obj?

    def __post_init__(self):
        super().__post_init__()
        self.src_list = [ipaddress.IPv4Address(src) for src in self.src_list]

@dataclass
class IGMPv3Query(Base):
    """ """
    type: IGMPType
    max_response_time: int
    checksum: int
    group: IPv4Address | str
    qqic: int
    suppress: bool
    querier_robustness: int
    querier_query_interval: int
    num_sources: int
    src_list: list[IPv4Address | str]

    def __post_init__(self):
        super().__post_init__()
        self.src_list = [ipaddress.IPv4Address(src) for src in self.src_list]


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
    """Used in MRT_ADD_VIF and MRT_DEL_VIF.  Based off the Linux struct: https://github.com/torvalds/linux/blob/master/include/uapi/linux/mroute.h#L61

        :param vifi: VIF index
        :param lcl_addr: Local interface address or index
        :param threshold: TTL threshold - minimum TTL packet must have to be forwarded on vif.  Typically, 1
        :param rate_limit Rate limiter values (Not Implemented in Linux)
        :param rmt_addr: IPIP tunnel address
    """
    vifi: int
    lcl_addr: IPv4Address | IPv6Address | str | int
    rmt_addr: IPv4Address | IPv6Address | str = ip_address("0.0.0.0")
    threshold: int = 1
    rate_limit: int = 0


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
    """Get the type from the type hint.

    :param type_obj: str | type: Specify that the type_obj parameter can be either a string or a type
    :return: The type of the argument
    """
    if isinstance(type_obj, type):
        return type_obj
    return eval(type_obj)
