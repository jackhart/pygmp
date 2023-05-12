"""This is not a daemon. It is a simple interactive shell to work with the MRT in a Linux kernel.

    This process takes the IGMP socket and can make changes to the MRT on-demand.  I use it for testing and experimentation.

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

import inspect
import socket
from inspect import Signature, Parameter, BoundArguments
from itertools import zip_longest
import sys
from contextlib import contextmanager
import threading
import queue

from pygmp import kernel, data
from pygmp.daemons.utils import get_logger


_logger = get_logger(__name__)


def main(args):

    with kernel.igmp_socket() as sock:
        _clean(sock)

        # create commands object with queue and socket
        commands = Commands(sock, queue.Queue())

        # start background thread to monitor socket
        thread = threading.Thread(target=_read_from_socket, args=(sock, commands.queue), daemon=True)
        thread.start()

        while True:
            with interactive_shell() as inputs:
                command, args = inputs
                commands.run_command(command, args)


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


class Commands:
    """Available commands: add vif, add mfc, del vif, del mfc, flush, status, msgs, bye help"""

    def __init__(self, sock: socket.socket, queuew: queue.Queue):
        self.sock = sock
        self.queue = queuew

    def run_command(self, command, args):
        fn = None
        try:
            fn = self._parse_command(command, args)
            signature = inspect.signature(fn)
            bn = Commands._parse_raw_arguments(args, signature)
        except TypeError as e:
            print(e)
            print(f"Usage: {fn.__doc__}" if fn else self.__doc__)
            return

        fn(**bn.arguments)

    def bye(self):
        """bye

            Exits the interactive shell.
        """
        exit(0)

    def list_vifs(self):
        """list vifs

            Prints contents of /proc/net/ip_mr_vif for the network namespace of the process.
        """
        print("\n")
        for vif in kernel.ip_mr_vif():
            print(vif)

    def list_mfc(self):
        """list mfc

            Prints contents of /proc/net/ip_mr_cache for the network namespace of the process.
        """
        print("\n")
        for mfc in kernel.ip_mr_cache():
            print(mfc)

    def help(self, command, subcommand=None):
        """help <command> [subcommand]

            Prints the docstring of the command.
        """
        try:
            print(self._parse_command(command, [subcommand] if subcommand else []).__doc__)
        except TypeError as e:
            print(e)

    def status(self):
        """status

            Prints the status of the MRT and PIM code in the kernel.
        """
        print(f"\nMR Version: {kernel.mrt_version(self.sock)}")
        print(f"\nPIM: {kernel.pim_is_enabled(self.sock)}")

    def flush(self):
        """flush

            Flushes the MRT.
        """
        kernel.flush(self.sock)

    def add_vif(self, vif_index: str, interface_addr_or_indx: str, remote_addr: str = "0.0.0.0", ttl_threshold: str = '1'):
        """add vif <vif_index> <interface_addr_or_indx> [remote_addr=0.0.0.0] [ttl_threshold=1]

            Creates a virtual interface device for multicast routing.

            vif_index: Interface index.  This must be a unique index for the new, multicast virtual interface.
            interface_addr_or_indx: Address or index of network interface.  Each multicast VIF maps to a unicast interface.
            remote_addr: IPIP tunnel address.  Not used in most cases.
            ttl_threshold: Minimum TTL value for multicast packets on this interface.
        """
        if interface_addr_or_indx.isdigit():
            interface_addr_or_indx = int(interface_addr_or_indx)

        vif_ctl = data.VifCtl(int(vif_index), interface_addr_or_indx, remote_addr, int(ttl_threshold), 0)
        kernel.add_vif(self.sock, vif_ctl)

    def add_mfc(self, origin: str, mcastgroup: str, parent: str, ttls: str = ""):
        """add mfc <origin> <group> <parent> [ttls='']

            Creates a multicast forwarding cache entry.

            origin: Source address of multicast packets.  Used for SSM ???  Optional?
            group: Multicast group address.
            parent: Interface index of incoming multicast interface.
            ttls: Comma separated list of TTL values.  TODO - more context.
        """
        ttls_lst = [int(ttl) for ttl in ttls.split(",")] if ttls else []
        mfc_ctl = data.MfcCtl(origin, mcastgroup, int(parent), ttls_lst)
        kernel.add_mfc(self.sock, mfc_ctl)

    def del_vif(self, vif_index: str):
        """del vif <vif_index>

            Deletes a virtual multicast interface device.

            vif_index: Unique interface index assigned with the add vif command.
        """
        vif_ctl = data.VifCtl(int(vif_index))
        kernel.del_vif(self.sock, vif_ctl)

    def del_mfc(self, origin: str, mcastgroup: str, parent: str):
        """del mfc <origin> <group> <parent>

            Deletes a multicast forwarding cache entry.

            origin: Source address of multicast packets.
            group: Multicast group address.
            parent: Interface index of incoming interface.

        """
        mfc_ctl = data.MfcCtl(origin, mcastgroup, int(parent))  # FIXME
        kernel.del_mfc(self.sock, mfc_ctl)

    def add_membership(self, multiaddr: str, interface: str):
        """add membership <multiaddr> <interface>

            multiaddr: multicast address.
            interface: interface address.  Must be a valid address on a host network interface.

            Runs setsockopt with IP_ADD_MEMBERSHIP option on the socket used for multicast routing.  This tells the kernel
            to join a multicast group on the specified interface.  The kernel initially sends an IGMP join message,
            then periodically sends IGMP membership reports.  When the socket is closed, the kernel will send
            an IGMP message to leave the group.

            This should not be necessary to do any multicast routing.  However, if your switch is configured with
            IGMP-snooping, sometimes IGMP messages are not properly forwarded to the router.
    """
        ip_mreq = data.IpMreq(multiaddr, interface)
        kernel.add_membership(self.sock, ip_mreq)

    def drop_membership(self, multiaddr: str, interface: str):
        """add membership <multiaddr> <interface>

            TODO - required fields?

            multiaddr: multicast address.
            interface: interface address.  Must be a valid address on a host network interface.

            Runs setsockopt with IP_DROP_MEMBERSHIP option on the socket used for multicast routing.  This tells the kernel
            to send an IGMP leave message and stop sending IGMP membership reports for the group.
    """
        ip_mreq = data.IpMreq(multiaddr, interface)
        kernel.drop_membership(self.sock, ip_mreq)

    def msgs(self):
        """msgs

            Prints any new messages from the kernel over the IGMP routing socket.
        """
        print(f"# New Messages: {self.queue.qsize()}")
        while not self.queue.empty():
            print(self.queue.get())

    def _parse_command(self, command: str, args: list[str]) -> callable:
        try:
            if command in {"list", "add", "del", "drop"}:
                command = f"{command}_{args.pop(0)}"

            fn = getattr(self, command)
        except AttributeError:
            raise TypeError(f"Unknown command: '{command.replace('_', ' ')}'")
        except IndexError:
            raise TypeError(f"Missing sub-command for command: '{command}'")
        return fn

    @staticmethod
    def _parse_raw_arguments(arguments: list[str], signature: Signature) -> BoundArguments:
        # TODO - cleanup
        args, kwargs = [], {}
        for param, arg in zip_longest(signature.parameters.values(), arguments):
            if param is None:
                if arg:
                    raise TypeError(f"too many arguments")
                break
            if param.default is Parameter.empty:
                if arg is None:
                    raise TypeError(f"{param.name} is a required argument")
                args.append(arg)
                continue

            if arg is None:
                break

            if "=" not in arg:
                raise TypeError(f"keyword argument must contain '=' for assignment")

            key, value = arg.split("=", 1)
            if key not in signature.parameters:
                raise TypeError(f"invalid keyword argument '{key}'")

            kwargs[key] = value

        ba = signature.bind(*args, **kwargs)
        ba.apply_defaults()
        return ba


def _clean(sock: kernel.InetRawSocketType):
    kernel.disable_pim(sock)
    kernel.enable_mrt(sock)
    kernel.flush(sock)


def _read_from_socket(sock, qu):
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


if __name__ == "__main__":
    main(sys.argv[1:])
