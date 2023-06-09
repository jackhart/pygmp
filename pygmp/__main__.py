"""Entrypoint for multicast routing daemon implementations."""
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

from fastapi import FastAPI
import uvicorn

from pygmp import kernel
from pygmp.daemons import simple


def build_args():
    # create the top-level parser
    parser = argparse.ArgumentParser(prog='Multicast Routing Daemons and Tools')
    parser.add_argument('--host', default="172.20.0.2", help='Host address for REST API')
    parser.add_argument('--port', default=8000, help='Port for REST API')

    subparsers = parser.add_subparsers(required=True, help='The multicast daemon or tool to run.')

    parser_a = subparsers.add_parser('simple', help='A simple multicast routing daemon.')
    parser_a.add_argument('--config', default="/etc/simple.ini", help='Config file for simple multicast routing daemon.')
    parser_a.set_defaults(daemon=simple.main)

    return parser.parse_args()


if __name__ == "__main__":
    with kernel.igmp_socket() as sock:
        args = build_args()
        app = args.daemon(sock, args, FastAPI())
        uvicorn.run(app, host=args.host, port=args.port)
