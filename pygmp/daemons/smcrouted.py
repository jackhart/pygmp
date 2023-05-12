"""Implementation of a static multicast routing daemon.

    Inspired and modeled after https://github.com/troglobit/smcroute

    TODO: a lot.
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

import os
import socket
from time import sleep
import signal
from dataclasses import dataclass, asdict

from pygmp.daemons.utils import DaemonContext, get_logger
from pygmp.daemons.config import load_config, Phyint, MRoute
from pygmp import kernel, data

logger = get_logger("daemon")


@dataclass
class VIF(Phyint):
    vifctl: data.VifCtl | None = None
    table_entry: data.VIFTableEntry | None = None

@dataclass
class MFC(MRoute):
    mfcctl: data.MfcCtl | None = None
    table_entry: data.MFCEntry | None = None


def main(args):
    signal.signal(signal.SIGTERM, program_cleanup)
    serve()


def serve(context: DaemonContext = None):

    config = load_config("/home/jack/Documents/projects/pygmp/tests/smcroute.ini")
    with kernel.igmp_socket() as sock:

        kernel.flush(sock)

        vifs_dict = join_vif_table(load_vifs(sock, config.phyint))
        mroutes_dict = join_mroute_table(load_mroutes(sock, config.mroute, vifs_dict))

        print(vifs_dict)
        print(mroutes_dict)

        while True:
            logger.info("And I wait until I'm told to die.")
            sleep(10)


def load_vifs(sock, phyints: list[Phyint]) -> dict[str, VIF]:

    vifs_dict = dict()
    for i, phyint in enumerate(phyints):
        vif = VIF(**asdict(phyint))

        vif.vifctl = data.VifCtl(vifi=i, lcl_addr=int(phyint.interface.index), threshold=int(phyint.ttl_threshold))
        kernel.add_vif(sock, vif.vifctl)
        vifs_dict[phyint.interface.name] = vif

    return vifs_dict


def join_vif_table(vifs_dict: dict[str, VIF]) -> dict[str, VIF]:

    vif_table = kernel.ip_mr_vif()

    if len(vif_table) != len(vifs_dict):
        raise RuntimeError("VIF table length mismatch")

    while vif_table:
        vif_entry = vif_table.pop()
        vifs_dict[vif_entry.interface].table_entry = vif_entry

    return vifs_dict


def load_mroutes(sock, mroutes: list[MRoute], vifs_dict: dict[str, VIF]) -> list[MFC]:
    mroute_set = list()
    print(mroutes)
    for i, mroute in enumerate(mroutes):
        mfc = MFC(**asdict(mroute))
        vif = vifs_dict[mroute.from_.interface.name]
        mfc.mfcctl = data.MfcCtl(origin=mroute.source,
                              mcastgroup=mroute.group,
                              parent=vif.vifctl.vifi,
                              ttls=_ttls_list(mroute.to, vifs_dict))
        kernel.add_mfc(sock, mfc.mfcctl)
        mroute_set.append(mfc)

    return mroute_set



def join_mroute_table(mroute_set: list[MFC]) -> list[MFC]:

    mfc_table = kernel.ip_mr_cache()
    print(mfc_table)
    print(mroute_set)
    if len(mfc_table) != len(mroute_set):
        raise RuntimeError("MFC length mismatch")

    # TODO
    # while mfc_table:
    #    mfc_entry = mfc_table.pop()

    return mroute_set


def _ttls_list(phyints: list[Phyint], vifs_dict: dict[str, VIF]) -> list[int]:

    ttls = [0] * len(vifs_dict)
    for inter in phyints:
        index = vifs_dict[inter.interface.name].vifctl.vifi
        ttls[index] = 1  # TODO - custom ttl for each phyint

    return ttls


def program_cleanup(signum, frame):
    # TODO - signals
    logger.info("My time has come.")
    exit(0)


def doman_socket():
    # TODO - interface
    server_address = './uds_socket'

    # Make sure the socket does not already exist
    try:
        os.unlink(server_address)
    except OSError:
        if os.path.exists(server_address):
            raise

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(server_address)
    sock.listen(1)

    while True:
        connection, client_address = sock.accept()
        try:
            while True:
                data = connection.recv(16)
                if data:
                    # process your data here
                    print('received {!r}'.format(data))
                else:
                    break
        finally:
            connection.close()

