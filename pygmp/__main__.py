"""Entrypoint for multicast routing daemon implementations."""

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