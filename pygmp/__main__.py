"""Entrypoint for multicast routing daemon implementations.

Usage::

    # Run in foreground (default)
    sudo python3 -m pygmp simple --config /etc/simple.ini

    # Run as a background daemon
    sudo python3 -m pygmp --daemon simple --config /etc/simple.ini

    # Specify host and port for the REST API
    sudo python3 -m pygmp --host 0.0.0.0 --port 9000 simple --config /etc/simple.ini
"""
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

import argparse
import sys

from fastapi import FastAPI
import uvicorn

from pygmp import kernel
from pygmp.daemons import simple


def build_args():
    """Build and parse command-line arguments.

    Returns:
        Parsed argparse.Namespace with all CLI options.
    """
    parser = argparse.ArgumentParser(
        prog='pygmp',
        description='Python IPv4 Multicast Routing Daemon with REST API')
    parser.add_argument('--host', default="0.0.0.0",
                        help='Host address for the REST API (default: 0.0.0.0)')
    parser.add_argument('--port', default=8000, type=int,
                        help='Port for the REST API (default: 8000)')
    parser.add_argument('--daemon', action='store_true', default=False,
                        help='Run as a background daemon (double-fork)')

    subparsers = parser.add_subparsers(required=True,
                                       help='The multicast daemon or tool to run.')

    parser_simple = subparsers.add_parser('simple',
                                          help='A simple static multicast routing daemon.')
    parser_simple.add_argument('--config', default="/etc/simple.ini",
                               help='Path to INI config file (default: /etc/simple.ini)')
    parser_simple.set_defaults(daemon_main=simple.main)

    return parser.parse_args()


if __name__ == "__main__":
    args = build_args()

    if args.daemon:
        from pygmp.daemons.utils import DaemonContext
        with DaemonContext():
            with kernel.igmp_socket() as sock:
                app = args.daemon_main(sock, args, FastAPI())
                uvicorn.run(app, host=args.host, port=args.port)
    else:
        with kernel.igmp_socket() as sock:
            app = args.daemon_main(sock, args, FastAPI())
            uvicorn.run(app, host=args.host, port=args.port)
