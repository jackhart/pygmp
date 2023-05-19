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


@dataclass
class MRoute:
    # TODO - support from address
    from_: data.Interface
    group: IPv4Address
    to: list[data.Interface]
    source: IPv4Address = ip_address("0.0.0.0")


@dataclass
class Config:
    phyint: list[data.Interface]
    mroute: list[MRoute]


def load_config(file_name: str) -> Config:

    config = configparser.ConfigParser()
    config.read(file_name)

    phyints =  _get_phyints(config)
    mroutes = _get_mroutes(config, phyints)
    return Config(phyint=phyints, mroute=mroutes)


def _get_mroutes(config_parser: configparser.ConfigParser, phyints: list[data.Interface]) -> list[MRoute]:
    pyints_dict = {p.name: p for p in phyints}
    mroutes = []
    for name in config_parser.sections():
        if name.startswith("mroute_"):
            ii = pyints_dict[config_parser.get(name, "from")]
            oil = [pyints_dict[inf] for inf in _str_list(config_parser.get(name, "to"))]
            group = _get_group_address(config_parser.get(name, "group"))
            source = ip_address(config_parser.get(name, "source", fallback="0.0.0.0"))
            mroutes.append(MRoute(from_=ii, group=group, to=oil, source=source))

    return mroutes


def _get_group_address(group_address: str) -> IPv4Address:
    group = ip_address(group_address)
    # TODO - prefix len
    if not group.is_multicast:
        raise ValueError(f"invalid group address {group_address}")

    return group


def _get_phyints(config_parser: configparser.ConfigParser):
    current_interfaces = kernel.network_interfaces()
    names = _str_list(config_parser.get("phyints", "names", fallback=""))
    return [_get_interface(current_interfaces, name) for name in names]


def _get_interface(interfaces, name):
    try:
        interface = interfaces[name]
    except KeyError:
        raise ValueError(f"phyint {name} does not exist")

    if not interface.addresses:
        raise ValueError(f"phyint {name} has no addresses")

    if  data.InterfaceFlags.MULTICAST not in interface.flags:
        raise ValueError(f"phyint {name} is not multicast capable")

    return interface


def _str_list(str_list: str) -> list[str]:
    return [s.strip() for s in str_list.split(',')]