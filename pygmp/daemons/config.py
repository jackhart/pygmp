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
from ipaddress import ip_address, IPv4Address
from dataclasses import dataclass

from pygmp import kernel, data


_DEFAULT_SOURCE = ip_address("0.0.0.0")
_MROUTE_PREFIX = "mroute_"


@dataclass
class MRoute:
    """Represents a multicast route."""
    from_: str
    group: IPv4Address
    to: dict[str, int]
    source: IPv4Address = _DEFAULT_SOURCE


@dataclass
class Config:
    phyint: list[data.Interface]
    mroute: list[MRoute]


def load_config(file_name: str) -> Config:
    config = configparser.ConfigParser()
    config.read(file_name)

    # TODO - better config validation
    phyints =  _parse_phyints(config)
    mroutes = _parse_mroutes(config)
    return Config(phyint=phyints, mroute=mroutes)


def _parse_mroutes(config_parser: configparser.ConfigParser) -> list[MRoute]:
    mroutes = []
    for name in config_parser.sections():
        if name.startswith(_MROUTE_PREFIX):
            outgoing_interface_dict = _parse_outgoing_map(config_parser.get(name, "to"))
            group = _parse_group_address(config_parser.get(name, "group"))
            source = ip_address(config_parser.get(name, "source", fallback="0.0.0.0"))
            mroutes.append(MRoute(from_=config_parser.get(name, "from"), group=group,
                                  to=outgoing_interface_dict, source=source))
    return mroutes


def _parse_phyints(config_parser: configparser.ConfigParser):
    """Parse physical interfaces from the configuration."""
    current_interfaces = kernel.network_interfaces()
    names = _str_to_list(config_parser.get("phyints", "names", fallback=""))
    return [_get_interface(current_interfaces, name) for name in names]


def _parse_group_address(group_address: str) -> IPv4Address:
    """Validate and convert group address to IPv4Address object."""
    group = ip_address(group_address) # TODO - prefix len support
    if not group.is_multicast:
        raise ValueError(f"Invalid group address {group_address}")

    return group


def _get_interface(interfaces, name):
    """Get interface by name and validate it."""
    try:
        interface = interfaces[name]
    except KeyError:
        raise ValueError(f"phyint {name} does not exist")

    if not interface.addresses:
        raise ValueError(f"phyint {name} has no addresses")

    if  data.InterfaceFlags.MULTICAST not in interface.flags:
        raise ValueError(f"phyint {name} is not multicast capable")

    return interface


def _parse_outgoing_map(to: str) -> dict[str, int]:
    return {inf: ttl for inf, ttl in
            (_str_to_key_value(inf_raw) for inf_raw in _str_to_list(to))}


def _str_to_key_value(str_pair: str, default_value=1) -> tuple[str, int]:
    """Convert a key=value string pair to a tuple."""
    parts = str_pair.split('=')
    if not parts[0].strip():
        raise ValueError(f"Invalid key: {str_pair}")

    value = int(parts[1].strip()) if len(parts) > 1 and parts[1].strip().isdigit() else default_value
    return parts[0].strip(), value


def _str_to_list(str_list: str) -> list[str]:
    return [s.strip() for s in str_list.split(',')]

