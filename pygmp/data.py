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
    """Base dataclass for all other dataclasses"""
    def __post_init__(self):
        for field in fields(self):
            if isinstance(_get_type(field.type), EnumMeta):
                setattr(self, field.name, _get_type(field.type)(getattr(self, field.name)))
            elif IPv4Address in set(get_args(_get_type(field.type))):
                if not isinstance(getattr(self, field.name), str):
                    continue
                setattr(self, field.name, ip_address(getattr(self, field.name)))


class IPVersion(Enum):
    """IP version"""
    IPv4 = 4  #: IP version 4
    IPv6 = 6  #: IP version 6


class IPProtocol(Enum):
    """IP message protocol."""
    CONTROL = 0  #: Control message sent by kernel over IGMP socket.  Has no IP protocol number.
    IGMP = 2  #: Internet Group Management Protocol (IGMP)
    PIM = 103  #: Protocol Independent Multicast (PIM)


class IGMPv3RecordType(Enum):
    """IGMPv3 Query Report record type"""
    MODE_IS_INCLUDE = 1  #: Response by interface in INCLUDE mode. Can receive traffic from the listed sources.
    MODE_IS_EXCLUDE = 2  #: Response by interface in EXCLUDE mode.  Ignoring traffic from the listed sources.
    CHANGE_TO_INCLUDE_MODE = 3  #: Interface changing to INCLUDE mode for multicast address.
    CHANGE_TO_EXCLUDE_MODE = 4  #: Interface changing to EXCLUDE mode for multicast address.
    ALLOW_NEW_SOURCES = 5  #: Either add new sources to the INCLUDE list or delete from the EXCLUDE list.
    BLOCK_OLD_SOURCES = 6  #: Either add new sources to the EXCLUDE list or delete from the INCLUDE list.


class IGMPType(Enum):
    """Internet Group Management Protocol (IGMP) message type"""
    MEMBERSHIP_QUERY = 0x11  #: Membership query
    V1_MEMBERSHIP_REPORT = 0x12  #: Version 1 membership report
    V2_MEMBERSHIP_REPORT = 0x16  #: Version 2 membership report
    V2_LEAVE_GROUP = 0x17  #: Version 2 Leave group
    V3_MEMBERSHIP_REPORT = 0x22  #: Version 3 membership report


class ControlMsgType(IntEnum):
    """Kernel's control message type"""
    IGMPMSG_NOCACHE = _kernel.IGMPMSG_NOCACHE  #: Got IGMP message for VIP with no matching multicast cache entry
    IGMPMSG_WRONGVIF = _kernel.IGMPMSG_WRVIFWHOLE  #: ... TODO
    IGMPMSG_WHOLEPKT = _kernel.IGMPMSG_WHOLEPKT  #:  ... TODO


class InterfaceFlags(IntEnum):
    """Linux network interface flags"""
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
    """Request structure for multicast socket operations."""
    format = "4s 4s"
    multiaddr: IPv4Address | IPv6Address | str #: IP multicast address of the group.
    interface: IPv4Address | IPv6Address | str #: Local IP address of the interface.


@dataclass
class VifReq(Base):
    """Data class for Virtual Interface (VIF) information used in `SIOCGETVIFCNT` ioctl call."""
    format = "HLLLL"
    vifi: int  #: VIF index
    icount: int = 0  #: Input packet count
    ocount: int = 0   #: Output packet count
    ibytes: int = 0  #: Input byte count
    obytes: int  = 0  #: Output byte count


@dataclass
class SGReq(Base):
    """Data class for 'Source-Group Request', used in `SIOCGETSGCNT` ioctl call."""
    format = "4s 4s LLL"
    src: IPv4Address | IPv6Address | str  #: Source IP address
    grp: IPv4Address | IPv6Address | str  #: Group IP address
    pktcnt: int = 0  #: Packet count
    bytecnt: int = 0  #: Byte count
    wrong_if: int = 0  #: Wrong interface count


@dataclass
class MfcCtl(Base):
    """Data class for Multicast Forwarding Cache (MFC) control, used in `MRT_ADD_MFC` and `MRT_DEL_MFC` calls."""
    origin: IPv4Address | IPv6Address | str  #: Originating IP address, used in Source-Specific Multicast (SSM)
    mcastgroup: IPv4Address | IPv6Address | str  #: Multicast group address
    parent: int  #: Parent VIF index, where the packet arrived (incoming interface index)
    ttls: list  #: List of minimum TTL thresholds for forwarding on VIFs
    expire: int = 0  #: Time in seconds after which the cache entry will be deleted  TODO - not supported


@dataclass
class Interface(Base):
    """Data class representing a network interface with all associated addresses."""
    name: str  #: Interface name
    index: int  #: Interface index
    flags: set[InterfaceFlags] | int  #: Interface flags
    addresses: set[str] = None  #: set of IP addresses associated with the interface

    def __post_init__(self):
        super().__post_init__()
        if isinstance(self.flags, int):
            self.flags = InterfaceFlags.from_value(self.flags)
        if self.addresses is None:
            self.addresses = set()


@dataclass
class IGMPControl(Base):
    """Data class representing the control message sent from kernel over the IGMP socket."""
    msgtype: ControlMsgType  #: Control message type
    mbz: int  #: Must be zero
    vif: int  #: Low 8 bits of VIF number
    vif_hi: int  #: High 8 bits of VIF number
    im_src: IPv4Address | IPv6Address | str   #: IP address of source of packet
    im_dst: IPv4Address | IPv6Address | str   #: IP address of destination of packet


@dataclass
class IPHeader(Base):
    """Data class representing an IP header."""
    version: IPVersion  #: IP version
    ihl: int  #: Internet Header Length
    tos: int  #: Type of service
    tot_len: int  #: Total length
    id: int  #: Identification
    frag_off: int  #: Fragment offset
    ttl: int  #: Time to live
    protocol: IPProtocol  #: IP Protocol
    check: int  #: Checksum
    src_addr: IPv4Address | IPv6Address | str  #: IP source address
    dst_addr: IPv4Address | IPv6Address | str  #: IP destination address


@dataclass
class IGMP(Base):
    """Data class representing the format of an IGMP message in an IP packet's payload."""
    type : IGMPType  #: IGMP version
    max_response_time: int  #: Maximum response time
    checksum: int  #: Checksum
    group: IPv4Address | str  #: Group address


@dataclass
class IGMPv3MembershipReport(Base):
    """Data class representing the format of an IGMP message in an IP packet's payload."""
    type: IGMPType  #: IGMP version
    checksum: int  #: Checksum
    num_records: int  #: Number of records
    grec_list: list[IGMPv3Record | dict]  #: List of records

    def __post_init__(self):
        super().__post_init__()
        self.grec_list = [IGMPv3Record(**grec) for grec in self.grec_list if isinstance(grec, dict)]


@dataclass
class IGMPv3Record(Base):
    """Data class representing a record in a IGMPv3 Membership Report messages."""
    type: IGMPv3RecordType  #: Record type
    auxwords: int  #: Auxiliary data length
    nsrcs: int  #: Number of sources
    mca: IPv4Address | str  #: Multicast address
    src_list: list[IPv4Address | str]  # Source address list

    def __post_init__(self):
        super().__post_init__()
        self.src_list = [ipaddress.IPv4Address(src) for src in self.src_list]


@dataclass
class IGMPv3Query(Base):
    """Data class representing an IGMPv3 Query."""
    type: IGMPType  #: IGMP type
    max_response_time: int  #: Maximum response time
    checksum: int  #: Checksum
    group: IPv4Address | str  #: Group address
    qqic: int  #: Querier's Query Interval Code
    suppress: bool  #: Suppress flag
    querier_robustness: int  #: Querier robustness variable
    querier_query_interval: int  #: Querier query interval
    num_sources: int  #: Number of sources
    src_list: list[IPv4Address | str]  #: Source list

    def __post_init__(self):
        super().__post_init__()
        self.src_list = [ipaddress.IPv4Address(src) for src in self.src_list]


@dataclass
class VIFTableEntry(Base):
    """Data class representing an entry in the VIF table at `/proc/net/ip_mr_vif`."""
    index: int  #: VIF index
    name: str  #: Interface name
    bytes_in: int  #: Number of bytes received
    pkts_in: int  #: Number of packets received
    bytes_out: int  #: Number of bytes transmitted
    pkts_out: int  #: Number of packets transmitted
    flags: int  #: Flags
    local_addr_or_interface: IPv4Address | IPv6Address | int  #: Local IP address or interface index
    remote_addr: IPv4Address | IPv6Address  #: IPIP tunnel address


@dataclass
class VifCtl(Base):
    """Data class used in `MRT_ADD_VIF` and `MRT_DEL_VIF`."""
    vifi: int  #: VIF index
    lcl_addr: IPv4Address | IPv6Address | str | int  #: Local interface address or index
    rmt_addr: IPv4Address | IPv6Address | str = ip_address("0.0.0.0")  #: IPIP tunnel address
    threshold: int = 1  #: TTL threshold
    rate_limit: int = 0  #: Rate limiter values (Not Implemented in Linux)


@dataclass
class MFCEntry(Base):
    """Data class representing an entry in the MFC table at `/proc/net/ip_mr_cache`."""
    group: IPv4Address | IPv6Address | str  #: Multicast group address
    origin: IPv4Address | IPv6Address | str  #: Originating IP address
    iif: int  #: Incoming interface index
    packets: int  #: Packet count
    bytes: int  #: Byte count
    wrong_if: int  #: Wrong incoming interface count
    oifs: dict[int, int]  #: Outgoing interface indices and their minimum TTLs for the route


def _get_type(type_obj: str | type) -> type:
    """Get the type from the type hint."""
    if isinstance(type_obj, type):
        return type_obj
    return eval(type_obj)
