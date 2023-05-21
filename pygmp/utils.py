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
import hashlib
import socket
from ipaddress import ip_address, IPv4Address, IPv6Address


def file_cache(filename):
    """Save the contents of a file to a cache, and only run the decorated function if the file has changed.
        This still has the overhead of reading the file.
    """
    def file_cache_wrapper(func):
        cache = {'last_hash': None, 'result': None}
        def wrapper():
            with open(filename, 'r') as f:
                content = f.read()
            new_hash = hashlib.md5(content.encode()).hexdigest()

            if new_hash != cache['last_hash']:
                cache['result'] = func()
                cache['last_hash'] = new_hash

            return cache['result']
        return wrapper
    return file_cache_wrapper


def host_hex_to_ip(hex_val: str) -> IPv4Address | IPv6Address:
    """Convert a hex string in network byte order (big-endian) to IP address object."""
    # Convert hex string to bytes
    net_order = bytes.fromhex(hex_val)

    if len(net_order) == 4:  # IPv4 address
        return ip_address(socket.inet_ntop(socket.AF_INET, net_order))
    elif len(net_order) == 16:  # IPv6 address
        return ip_address(socket.inet_ntop(socket.AF_INET6, net_order))
    else:
        raise ValueError(f"Invalid IP address length: {len(net_order)}")
