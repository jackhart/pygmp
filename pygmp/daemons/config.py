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
class Phyint:
    interface: data.Interface
    state: bool = False
    ttl_threshold: int = 1


@dataclass
class MRoute:
    # TODO - support from address
    from_: Phyint
    group: IPv4Address
    to: list[Phyint]
    source: IPv4Address = ip_address("0.0.0.0")


@dataclass
class Config:
    phyint: list[Phyint]
    mroute: list[MRoute]


def load_config(file_name: str) -> Config:

    config = configparser.ConfigParser()
    config.read(file_name)

    phyints =  _get_phyints(config)
    mroutes = _get_mroutes(config, phyints)
    return Config(phyint=phyints, mroute=mroutes)



def _get_phyints(config_parser: configparser.ConfigParser) -> list[Phyint]:
    current_interfaces = kernel.network_interfaces()
    return [Phyint(interface=_get_interface(current_interfaces, name[7:]),
                   state=config_parser[name].getboolean("enabled", fallback=True),
                   ttl_threshold=config_parser[name].getint("ttl_threshold", fallback=1))
            for name in config_parser.sections() if name.startswith("phyint_")]


def _get_mroutes(config_parser: configparser.ConfigParser, phyints: list[Phyint]) -> list[MRoute]:
    pyints_dict = {p.interface.name: p for p in phyints}
    mroutes = []
    for name in config_parser.sections():
        if name.startswith("mroute_"):
            config = config_parser[name]
            incoming_interface = _get_phyint(config.get("from"), pyints_dict=pyints_dict)
            outgoing_interfaces = [_get_phyint(i.strip(), pyints_dict) for i in config_parser[name].get("to").split(',')]
            group = _get_group_address(config.get("group"))
            source = ip_address(config.get("source", fallback="0.0.0.0"))
            mroutes.append(MRoute(from_=incoming_interface, group=group, to=outgoing_interfaces, source=source))

    return mroutes


def _get_group_address(group_address: str) -> IPv4Address:
    group = ip_address(group_address)
    # TODO - prefix len
    if not group.is_multicast:
        raise ValueError(f"invalid group address {group_address}")

    return group


def _get_phyint(phyint_name, pyints_dict):

    if phyint_name not in pyints_dict:
        raise ValueError(f"phyint {phyint_name} not defined")

    if not pyints_dict[phyint_name].state:
        raise ValueError(f"phyint {phyint_name} not enabled")

    return pyints_dict[phyint_name]


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
