import os
from ipaddress import ip_address, IPv4Address, IPv6Address

from pygmp.kernel.data import IPHeader, IGMPControl, IGMP, Interface, VIFTableEntry, MFCEntry
from pygmp.kernel import _kernel


def parse_ip_header(buffer: bytes):
    return IPHeader(**_kernel.parse_ip_header(buffer))


def parse_igmp(buffer: bytes):
    return IGMP(**_kernel.parse_igmp(buffer))


def parse_igmp_control(buffer: bytes):
    return IGMPControl(**_kernel.parse_igmp_control(buffer))


def network_interfaces() -> dict[str, Interface]:
    """Get list of VIFs from kernel.  Returns the name, IP address, and if multicast is enabled."""
    interfaces = dict()
    for inf in _kernel.network_interfaces():
        if inf["name"] not in interfaces:
            interfaces[inf["name"]] = Interface(inf["name"], inf["index"], inf["flags"], [inf["address"]])
        else:  # FIXME - any edge case where flags are different but name is the same?
            interfaces[inf["name"]].addresses.append(inf["address"])

    return interfaces


def ip_mr_vif() -> list[VIFTableEntry]:
    """Parse the /proc/net/ip_mr_vif file.  Linux specific, holds the IPv4 virtual interfaces used by the active multicast routing daemon.

        Virtual file generated by the kernel code here: https://github.com/torvalds/linux/blob/master/net/ipv4/ipmr.c#L2922
            interface bytesin pktsin bytesout pktsout flags local remote
            %2td %-10s %8ld %7ld  %8ld %7ld %05X %08X %08X

        Raises FileNotFoundError if the file does not exist.

        FIXME - local_address will be index if MRT_ADD_VIF is called with one.

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
    """
    host_order = bytearray.fromhex(hex_val)
    host_order.reverse()
    big_endian = bytes(host_order)
    return ip_address(big_endian)

def _parse_index_ttl(pairs_list: list[str]) -> dict[int, int]:
    """Parse a list of index:ttl pairs into a dictionary."""
    return {int(pair.split(':')[0]): int(pair.split(':')[1]) for pair in pairs_list}
