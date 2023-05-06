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

from socket import SocketType
from typing import Any, Final


MRT_INIT: Final[int]
MRT_DONE: Final[int]
MRT_ADD_VIF: Final[int]
MRT_DEL_VIF: Final[int]
MRT_ADD_MFC: Final[int]
MRT_DEL_MFC: Final[int]
MRT_VERSION: Final[int]
MRT_ASSERT: Final[int]
MRT_PIM: Final[int]
MRT_TABLE: Final[int]
MRT_ADD_MFC_PROXY: Final[int]
MRT_DEL_MFC_PROXY: Final[int]
MRT_FLUSH: Final[int]
MRT_MAX: Final[int]
MRT_FLUSH_MFC: Final[int]
MRT_FLUSH_MFC_STATIC: Final[int]
MRT_FLUSH_VIFS: Final[int]
MRT_FLUSH_VIFS_STATIC: Final[int]
IGMPMSG_NOCACHE: Final[int]
IGMPMSG_WHOLEPKT: Final[int]
IGMPMSG_WRVIFWHOLE: Final[int]
VIFF_TUNNEL: Final[int]
VIFF_SRCRT: Final[int]
VIFF_REGISTER: Final[int]
VIFF_USE_IFINDEX: Final[int]
MAXVIFS: Final[int]
SIOCGETVIFCNT: Final[int]
SIOCGETSGCNT: Final[int]
SIOCGETRPF: Final[int]


def network_interfaces() -> list[dict[str, Any]]:
    ...

def add_mfc(sock: SocketType, src_str: str, grp_str: str, parent_vif: int, ttls: list[int]) -> None:
    ...

def del_mfc(sock: SocketType, src_str: str, grp_str: str, parent_vif: int) -> None:
    ...

def add_vif(sock: SocketType, vifi: int, threshold: int, rate_limit: int, lcl_addr: str, rmt_addr: str) -> None:
    ...

def del_vif(sock: SocketType, vifi: int) -> None:
    ...

def parse_igmp_control(buffer: bytes) -> dict[str, Any]:
    ...

def parse_ip_header(buffer: bytes) -> dict[str, Any]:
    ...

def parse_igmp(buffer: bytes) -> dict[str, Any]:
    ...
