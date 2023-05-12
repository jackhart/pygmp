from random import randint
import pytest
import socket
from scapy.all import *
from scapy.all import IP, ICMP, sr1
from time import sleep

from pygmp import kernel, data


@pytest.fixture
def packet():
    ip_header = IP(src="30.0.0.1", dst="239.0.0.3", ttl=3, flags=2, id=randint(1, 65535))
    icmp_payload = ICMP(type=8, code=0, id=100, seq=1, chksum=None)
    return ip_header / icmp_payload


@pytest.fixture
def raw_socket():
    sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
    yield sock
    sock.close()


@pytest.fixture
def igmp_sock():
    with kernel.igmp_socket() as sock:
        yield sock

@pytest.fixture
def cleaned_igmp_sock(igmp_sock):
    kernel.disable_pim(igmp_sock)
    kernel.flush(igmp_sock)
    kernel.enable_mrt(igmp_sock)

    yield igmp_sock
    kernel.flush(igmp_sock)


@pytest.fixture(autouse=True)
def setup_simple_vifs(cleaned_igmp_sock):
    kernel.add_vif(cleaned_igmp_sock,  data.VifCtl(vifi=0, lcl_addr="10.0.0.1", threshold=1))
    kernel.add_vif(cleaned_igmp_sock,  data.VifCtl(vifi=1, lcl_addr="20.0.0.1", threshold=1))
    kernel.add_vif(cleaned_igmp_sock,  data.VifCtl(vifi=2, lcl_addr="30.0.0.1", threshold=1))



def test_simple_route(raw_socket, packet, cleaned_igmp_sock):

    kernel.add_mfc(cleaned_igmp_sock, data.MfcCtl(origin="10.0.0.1", mcastgroup="239.0.0.2", parent=0, ttls=[0,1,0]))

    packet_bytes = raw(_new_packet(packet, "10.0.0.1", "239.0.0.2"))

    raw_socket.bind(("10.0.0.1", 0))
    raw_socket.sendto(packet_bytes, ("239.0.0.2", 0))
    sleep(1)

    new_vifs = _get_vifs_map()
    new_mr_cache = kernel.ip_mr_cache()

    assert new_vifs[0].pkts_in == 1 and new_vifs[0].pkts_out == 0
    assert new_vifs[1].pkts_in == 0 and new_vifs[1].pkts_out == 1
    assert new_vifs[2].pkts_in == 0 and new_vifs[2].pkts_out == 0
    assert new_mr_cache[0].packets == 1


def test_ssm_route(raw_socket, packet, cleaned_igmp_sock):
    kernel.add_mfc(cleaned_igmp_sock, data.MfcCtl(origin="30.0.0.1", mcastgroup="239.0.0.2", parent=0, ttls=[0,1,0]))

    packet_bytes = raw(_new_packet(packet, "30.0.0.1", "239.0.0.2"))

    raw_socket.bind(("10.0.0.1", 0))  # ON a1 (with a3 source address)
    raw_socket.sendto(packet_bytes, ("239.0.0.2", 0))
    sleep(1)

    new_vifs = _get_vifs_map()
    new_mr_cache = kernel.ip_mr_cache()

    assert new_vifs[0].pkts_in == 1 and new_vifs[0].pkts_out == 0
    assert new_vifs[1].pkts_in == 0 and new_vifs[1].pkts_out == 1
    assert new_vifs[2].pkts_in == 0 and new_vifs[2].pkts_out == 0
    assert new_mr_cache[0].packets == 1


def _get_vifs_map() -> dict[int, data.VIFTableEntry]:
    return {vif.index: vif for vif in kernel.ip_mr_vif()}


def _new_packet(packet, src: str, dst: str):
    packet.src = src
    packet.dst = dst
    return packet

