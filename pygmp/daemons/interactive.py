"""This is not a daemon. It is a simple interactive shell to work with the MRT in a Linux kernel.

    This process takes the IGMP socket and can make changes to the MRT on-demand.  I use it for testing and experimentation.

"""
import inspect
import sys
from contextlib import contextmanager
import threading
import queue

from pygmp import kernel, data
from pygmp.daemons.utils import get_logger


_logger = get_logger(__name__)


def main(args):

    q = queue.Queue()
    with kernel.igmp_socket() as sock:

        # initial setup.
        _clean(sock)

        # start background thread to read from socket and append to queue
        thread = threading.Thread(target=read_from_socket, args=(sock, q), daemon=True)
        thread.start()

        while True:
            with interactive_shell() as inputs:
                command, args = inputs

                if command == "exit":
                    exit(0)

                if command == "status:":
                    print(f"\nMR Version: {kernel.mrt_version(sock)}")
                    print(f"\nPIM: {kernel.pim_is_enabled(sock)}")

                elif command == "flush":
                    kernel.flush(sock)

                elif command == "list":
                    _list(*args)

                elif command == "add":
                    sub_command, sub_args = _get_subcommand_and_args(args)
                    _add(sock, sub_command, sub_args)

                elif command == "del":
                    sub_command, sub_args = _get_subcommand_and_args(args)
                    _del(sock, sub_command, sub_args)

                elif command == "msgs":
                    while not q.empty():
                        print(q.get())

                else:
                    print(f"Unknown command: '{command}'")
                    print("Available commands: list <vifs|mfc>, add <vif|mfc|membership>, del <vif|mfc>, msgs, flush, exit")


@contextmanager
def interactive_shell():
    try:
        # Get input from user
        raw_input = input("> ")
        command, *args = raw_input.strip().split(" ")
        yield command, args

    except KeyboardInterrupt:
        _logger.warning("Keyboard interrupt. Exiting.")
        exit(0)
    except Exception:
        _logger.exception("Unknown error. Please report.")


def assert_args(fn):
    def wrapper(*args):
        # FIXME - arg count off by one when socket is passed in.
        arg_num = len(inspect.signature(fn).parameters)
        if len(args) != arg_num:
            print("Invalid number of arguments. Expected {}, got {}".format(arg_num, len(args)))
            print("Usage: {}".format(fn.__doc__))
            return None
        return fn(*args)
    return wrapper


def read_from_socket(sock, qu):
    try:
        while True:
            buff, _ = sock.recvfrom(6000) # FIXME - buffer size
            qu.put(_filter_ip(kernel.parse_ip_header(buff), buff))
    except Exception:
        _logger.exception("Error in read_from_socket thread.  This will be ignored.")


def _filter_ip(ip_header: data.IPHeader, buffer: bytes):
    if ip_header.protocol == data.IPProtocol.IGMP:
        return kernel.parse_igmp(buffer[ip_header.ihl * 4:])
    if ip_header.protocol == data.IPProtocol.CONTROL:
        return kernel.parse_igmp_control(buffer)
    _logger.warning("warning, skipping packet...")


@assert_args
def _add_vif(sock, vif_index: str, ttl_threshold: str, rate_limit: str, interface_addr: str, remote_addr: str):
    """add vif <index> <ttl_threshold> <rate_limit> <interface_addr> <remote_addr>"""
    if interface_addr.isdigit():
        interface_addr = int(interface_addr)

    vif_ctl = data.VifCtl(int(vif_index), int(ttl_threshold), int(rate_limit), interface_addr, remote_addr)
    kernel.add_vif(sock, vif_ctl)


@assert_args
def _add_mfc(sock, origin: str, mcastgroup: str, parent: str, ttls: str):
    """add mfc <origin> <group> <parent> <ttls>"""
    mfc_ctl = data.MfcCtl(origin, mcastgroup, int(parent), [int(ttl) for ttl in ttls.split(",")])
    kernel.add_mfc(sock, mfc_ctl)


@assert_args
def _del_vif(sock, vif_index: str):
    """del vif <index>"""
    vif_ctl = data.VifCtl(int(vif_index))
    kernel.del_vif(sock, vif_ctl)


@assert_args
def _del_mfc(sock, origin: str, mcastgroup: str, parent: str):
    """del mfc <origin> <group> <parent>"""
    mfc_ctl = data.MfcCtl(origin, mcastgroup, int(parent))  # FIXME
    kernel.del_mfc(sock, mfc_ctl)


@assert_args
def _add_membership(sock, multiaddr: str, interface: str):
    """add membership <multiaddr> <interface>"""
    ip_mreq = data.IpMreq(multiaddr, interface)
    kernel.add_membership(sock, ip_mreq)


@assert_args
def _list(sub_command: str):
    """list <vifs|mfc>"""
    if sub_command == "vifs":
        _print_vifs()
    elif sub_command == "mfc":
        _print_mfc()
    else:
        print(f"list {sub_command} is not a valid command.  Usage: {_list.__doc__}")


@assert_args
def _add(sock, sub_command: str, args: list | tuple):
    """add <vif|mfc|membership>"""
    if sub_command == "vif":
        _add_vif(sock, *args)

    elif sub_command == "mfc":
        _add_mfc(sock, *args)

    elif sub_command == "membership":
        _add_membership(sock, *args)

    else:
        print(f"'add {sub_command}' is not a valid command.  Usage: add <vif|mfc>")

@assert_args
def _del(sock, sub_command: str, args: list | tuple):
    """del <vif|mfc>"""
    if sub_command == "vif":
        _del_vif(sock, *args)

    elif sub_command == "mfc":
        _del_mfc(sock, *args)

    else:
        print(f"'del {sub_command}' is not a valid command.  Usage: del <vif|mfc>")


def _get_subcommand_and_args(args):
    if len(args) == 0:
        return "", []
    sub_command, *sub_args = args
    return sub_command, sub_args


def _clean(sock: kernel.InetRawSocketType):
    kernel.disable_pim(sock)
    kernel.enable_mrt(sock)
    kernel.flush(sock)


def _print_vifs():
    print("\n")
    for vif in kernel.ip_mr_vif():
        print(vif)


def _print_mfc():
    print("\n")
    for mfc in kernel.ip_mr_cache():
        print(mfc)


if __name__ == "__main__":
    main(sys.argv[1:])
