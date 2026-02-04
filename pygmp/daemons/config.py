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
import configparser
from ipaddress import ip_address, ip_network, IPv4Address, IPv4Network
from dataclasses import dataclass, field

from pygmp import kernel, data


_DEFAULT_SOURCE = ip_address("0.0.0.0")
_MROUTE_PREFIX = "mroute_"


@dataclass
class MRoute:
    """Represents a multicast route.

    Attributes:
        from_: Source interface name (where multicast packets arrive).
        group: Multicast group address (single IPv4Address or IPv4Network for wildcard routes).
        to: Dictionary mapping destination interface names to TTL threshold values.
        source: Source IP address for Source-Specific Multicast (SSM). Defaults to 0.0.0.0
            which means any source (wildcard/dynamic route).
    """
    from_: str
    group: IPv4Address | IPv4Network
    to: dict[str, int] = field(default_factory=dict)
    source: IPv4Address = _DEFAULT_SOURCE

    def matches_group(self, group_addr: IPv4Address | str) -> bool:
        """Check if a multicast group address matches this route's group.

        Supports both exact address matching and CIDR prefix matching.

        Args:
            group_addr: The multicast group address to check.

        Returns:
            True if the address matches.
        """
        if isinstance(group_addr, str):
            group_addr = ip_address(group_addr)
        if isinstance(self.group, IPv4Network):
            return group_addr in self.group
        return group_addr == self.group


@dataclass
class Config:
    """Parsed daemon configuration.

    Attributes:
        phyint: List of physical network interfaces to use for multicast routing.
        mroute: List of multicast route definitions.
    """
    phyint: list[data.Interface]
    mroute: list[MRoute]


def load_config(file_name: str) -> Config:
    """Load and parse a daemon configuration file.

    Args:
        file_name: Path to the INI configuration file.

    Returns:
        Parsed Config object.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If the config file contains invalid values.
        configparser.Error: If the config file is malformed.
    """
    config = configparser.ConfigParser()
    files_read = config.read(file_name)
    if not files_read:
        raise FileNotFoundError(f"Configuration file not found: {file_name}")

    phyints = _parse_phyints(config)
    mroutes = _parse_mroutes(config, [iface.name for iface in phyints])
    return Config(phyint=phyints, mroute=mroutes)


def _parse_mroutes(config_parser: configparser.ConfigParser,
                   known_interfaces: list[str] | None = None) -> list[MRoute]:
    """Parse all mroute sections from the config.

    Args:
        config_parser: The parsed INI config.
        known_interfaces: Optional list of known interface names for validation.

    Returns:
        List of parsed MRoute objects.
    """
    mroutes = []
    for name in config_parser.sections():
        if name.startswith(_MROUTE_PREFIX):
            outgoing_interface_dict = _parse_outgoing_map(config_parser.get(name, "to"))
            group = _parse_group_address(config_parser.get(name, "group"))
            source = ip_address(config_parser.get(name, "source", fallback="0.0.0.0"))
            from_iface = config_parser.get(name, "from")

            if known_interfaces:
                if from_iface not in known_interfaces:
                    raise ValueError(
                        f"Route '{name}': source interface '{from_iface}' "
                        f"not in configured phyints: {known_interfaces}")
                for to_iface in outgoing_interface_dict:
                    if to_iface not in known_interfaces:
                        raise ValueError(
                            f"Route '{name}': destination interface '{to_iface}' "
                            f"not in configured phyints: {known_interfaces}")

            mroutes.append(MRoute(from_=from_iface, group=group,
                                  to=outgoing_interface_dict, source=source))
    return mroutes


def _parse_phyints(config_parser: configparser.ConfigParser) -> list[data.Interface]:
    """Parse physical interfaces from the configuration.

    Validates that each named interface exists, has addresses, and is multicast-capable.

    Args:
        config_parser: The parsed INI config.

    Returns:
        List of validated Interface objects.

    Raises:
        ValueError: If an interface doesn't exist, has no addresses, or isn't multicast capable.
    """
    current_interfaces = kernel.network_interfaces()
    names_str = config_parser.get("phyints", "names", fallback="")
    if not names_str.strip():
        return []
    names = _str_to_list(names_str)
    return [_get_interface(current_interfaces, name) for name in names]


def _parse_group_address(group_address: str) -> IPv4Address | IPv4Network:
    """Validate and convert a group address string to an IPv4Address or IPv4Network.

    Supports both single addresses (e.g. '239.0.0.1') and CIDR notation
    (e.g. '239.1.0.0/24') for wildcard group matching.

    Args:
        group_address: Multicast group address string, optionally with CIDR prefix.

    Returns:
        IPv4Address for exact matches, IPv4Network for prefix/wildcard matches.

    Raises:
        ValueError: If the address is not a valid multicast address/network.
    """
    if '/' in group_address:
        network = ip_network(group_address, strict=False)
        # Validate that the network is within the multicast range (224.0.0.0 - 239.255.255.255)
        if not network.network_address.is_multicast:
            raise ValueError(f"Invalid multicast network: {group_address}")
        return network

    group = ip_address(group_address)
    if not group.is_multicast:
        raise ValueError(f"Invalid multicast group address: {group_address}")
    return group


def _get_interface(interfaces, name):
    """Get interface by name and validate it.

    Args:
        interfaces: Dictionary of available network interfaces.
        name: Interface name to look up.

    Returns:
        The validated Interface object.

    Raises:
        ValueError: If the interface doesn't exist, has no addresses, or isn't multicast capable.
    """
    try:
        interface = interfaces[name]
    except KeyError:
        raise ValueError(f"phyint '{name}' does not exist")

    if not interface.addresses:
        raise ValueError(f"phyint '{name}' has no addresses")

    if data.InterfaceFlags.MULTICAST not in interface.flags:
        raise ValueError(f"phyint '{name}' is not multicast capable")

    return interface


def _parse_outgoing_map(to: str) -> dict[str, int]:
    """Parse outgoing interface map from config string.

    Format: 'iface1=ttl,iface2=ttl' or 'iface1,iface2' (default TTL of 1).

    Args:
        to: Comma-separated interface=ttl pairs.

    Returns:
        Dictionary mapping interface names to TTL values.
    """
    return {inf: ttl for inf, ttl in
            (_str_to_key_value(inf_raw) for inf_raw in _str_to_list(to))}


def _str_to_key_value(str_pair: str, default_value=1) -> tuple[str, int]:
    """Convert a key=value string pair to a tuple.

    Args:
        str_pair: String in 'key=value' or 'key' format.
        default_value: Value to use if no '=value' is provided.

    Returns:
        Tuple of (key, value).

    Raises:
        ValueError: If the key is empty.
    """
    parts = str_pair.split('=')
    if not parts[0].strip():
        raise ValueError(f"Invalid key: {str_pair}")

    value = int(parts[1].strip()) if len(parts) > 1 and parts[1].strip().isdigit() else default_value
    return parts[0].strip(), value


def _str_to_list(str_list: str) -> list[str]:
    """Split a comma-separated string into a list of stripped strings."""
    return [s.strip() for s in str_list.split(',') if s.strip()]
