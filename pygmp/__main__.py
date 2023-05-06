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
from pygmp.daemons import interactive, smcrouted


def build_args():
    # create the top-level parser
    parser = argparse.ArgumentParser(prog='Multicast Routing Daemons and Tools')
    # parser.add_argument('--foo', action='store_true', help='foo help')
    subparsers = parser.add_subparsers(required=True, help='The multicast daemon or tool to run.')

    parser_a = subparsers.add_parser('interactive', help=interactive.__doc__)
    parser_a.set_defaults(daemon=interactive.main)
    # parser_b.add_argument('--baz', choices='XYZ', help='baz help')

    parser_b = subparsers.add_parser('smcrouted', help='b help')
    parser_b.set_defaults(daemon=smcrouted.main)

    return parser.parse_args()


def main():
    args = build_args()
    args.daemon(args)


if __name__ == "__main__":
    main()