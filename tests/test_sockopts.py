import pytest
import socket

from pygmp.kernel import sockopts
from pygmp.kernel import data


# TODO - get these from the system calls.
# TODO - setup networking test structure
_IFREQ_BYTES = b'\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
_VIFCTL_BYTES = b'\x01\x00\x02\x03\x04\x00\x00\x00\n\n\x00\x01\xef\x00\x00\x04'
_VIFCTLINX_BYTES = b'\x01\x00\x02\x03\x04\x00\x00\x00\x00\x00\x00\x00\xef\x00\x00\x04'
_MFCTL_BYTES = (b'\n\n\x00\x01\xef\x00\x00\x04\x03\x00\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01'
                b'\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01'
                b'\x01\x01\x01\x01\x01\x01\x00\x00\x05\x00\x00\x00\x06\x00\x00\x00'
                b'\x07\x00\x00\x00\x08\x00\x00\x00')
_IGMPMSG_BYTES = b'E\x00\x00\x1c\x00\x00@\x00\x01\x00\x00\x00\n\x00\x00\x01\xef\x00\x00\x04\x01\x00\x00\x00\x00\x00\x00\x00'
_IGMP_IP_PACKET = b'F\xc0\x00 \x00\x00@\x00\x01\x02\xeb\x14\n\x00\x00\x01\xef\x00\x00\x02\x94\x04\x00\x00\x16\x00\xfa\xfc\xef\x00\x00\x02'


@pytest.fixture
def vif_a1():
    return {"name": "a1", "address": "10.0.0.1", "ifindx": 6}


@pytest.fixture
def vif_a2():
    return {"name": "a2", "address": "20.0.0.1", "ifindx": 7}


@pytest.fixture
def multicast_addr():
    return "239.0.0.4"


@pytest.fixture
def sock():
    with sockopts.igmp_socket() as sock:
        yield sock

@pytest.fixture
def cleaned_sock(sock):
    sockopts.disable_pim(sock)
    sockopts.enable_mrt(sock)
    sockopts.flush(sock)

    yield sock
    sockopts.flush(sock)


def test_mrt_version(cleaned_sock):
    assert sockopts.mrt_version(cleaned_sock) == hex(0x0305)


def test_enable_mrt_unclean(sock):
    sockopts.enable_mrt(sock)


def test_enable_mrt(cleaned_sock):
    # it should be enabled already and throw this error.
    with pytest.raises(OSError):
        sockopts.enable_mrt(cleaned_sock)


def test_disable_mrt_unclean(sock):
    with pytest.raises(OSError):
        sockopts.disable_mrt(sock)


def test_disable_mrt(cleaned_sock):
    sockopts.disable_mrt(cleaned_sock)
    sockopts.enable_mrt(cleaned_sock)


def test_enable_pim(sock):
    # TODO - not clear how to validate this.
    sockopts.enable_pim(sock)


def test_disable_pim(cleaned_sock):
    # TODO - not clear how to validate this.
    sockopts.disable_pim(cleaned_sock)


def test_add_vif(cleaned_sock, vif_a1, multicast_addr):
    vif_ctl = data.VifCtl(1, 1, 0, vif_a1["address"], multicast_addr)
    sockopts.add_vif(cleaned_sock, vif_ctl)

    with pytest.raises(OSError):
        sockopts.add_vif(cleaned_sock, vif_ctl)


def test_add_vif_by_index(cleaned_sock, vif_a1, multicast_addr):
    vif_ctl = data.VifCtl(1, 1, 0, str(vif_a1["ifindx"]), multicast_addr)
    sockopts.add_vif(cleaned_sock, vif_ctl)


def test_add_remove_vif(cleaned_sock, vif_a1, multicast_addr):
    vif_ctl = data.VifCtl(1, 1, 0, vif_a1["address"], multicast_addr)
    sockopts.add_vif(cleaned_sock, vif_ctl)
    sockopts.del_vif(cleaned_sock, vif_ctl)

    with pytest.raises(OSError):
        sockopts.del_vif(cleaned_sock, vif_ctl)


def test_get_vif_counts(cleaned_sock, vif_a1, multicast_addr):
    vif_ctl = data.VifCtl(1, 1, 0, vif_a1["address"], multicast_addr)
    sockopts.add_vif(cleaned_sock, vif_ctl)

    vif_req = data.VifReq(1)
    vif_req_new = sockopts.get_vif_counts(cleaned_sock, vif_req)
    assert vif_req_new.icount == 0
    assert vif_req_new.ocount == 0
    assert vif_req_new.ibytes == 0
    assert vif_req_new.obytes == 0


def test_get_mfc_counts(cleaned_sock, vif_a1, vif_a2, multicast_addr):
    vif_ctl = data.VifCtl(1, 1, 0, vif_a1["address"], "0.0.0.0")
    sockopts.add_vif(cleaned_sock, vif_ctl)

    vif_ctl = data.VifCtl(2, 1, 0, vif_a2["address"], "0.0.0.0")
    sockopts.add_vif(cleaned_sock, vif_ctl)

    mfc_ctl = data.MfcCtl(vif_a1["address"], multicast_addr, 1, [0, 1, 1])
    sockopts.add_mfc(cleaned_sock, mfc_ctl)

    mfc_req = data.SGReq(vif_a1["address"], multicast_addr)
    mfc_req_new = sockopts.get_mfc_counts(cleaned_sock, mfc_req)
    print(mfc_req_new)


def test_get_vif_counts_error(cleaned_sock):
    with pytest.raises(OSError):
        vif_req = data.VifReq(1)
        _ = sockopts.get_vif_counts(cleaned_sock, vif_req)


def test_add_mfc(cleaned_sock, vif_a1, multicast_addr):
    # add VIF
    vif_ctl = data.VifCtl(1, 1, 0, vif_a1["address"], multicast_addr)
    sockopts.add_vif(cleaned_sock, vif_ctl)

    # add route
    mfc_ctl = data.MfcCtl(vif_a1["address"], multicast_addr, 1, [0, 1])
    sockopts.add_mfc(cleaned_sock, mfc_ctl)


def test_del_mfc(cleaned_sock, vif_a1, multicast_addr):
    # add VIF
    vif_ctl = data.VifCtl(1, 1, 0, vif_a1["address"], multicast_addr)
    sockopts.add_vif(cleaned_sock, vif_ctl)

    # add route
    mfc_ctl = data.MfcCtl(vif_a1["address"], multicast_addr, 1, [0, 1])
    sockopts.add_mfc(cleaned_sock, mfc_ctl)

    # delete route
    sockopts.del_mfc(cleaned_sock, mfc_ctl)


def test_flush(cleaned_sock, vif_a1, multicast_addr):
    # add VIF
    vif_ctl = data.VifCtl(1, 1, 0, vif_a1["address"], multicast_addr)
    sockopts.add_vif(cleaned_sock, vif_ctl)

    # add route
    mfc_ctl = data.MfcCtl(vif_a1["address"], multicast_addr, 1, [0, 1])
    sockopts.add_mfc(cleaned_sock, mfc_ctl)

    # flush
    sockopts.flush(cleaned_sock)

    # add VIF - won't throw error
    vif_ctl = data.VifCtl(1, 1, 0, vif_a1["address"], multicast_addr)
    sockopts.add_vif(cleaned_sock, vif_ctl)


def test_add_membership(multicast_addr, vif_a1):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ip_mreq = data.IpMreq(multicast_addr, vif_a1["address"])
    sockopts.add_membership(sock, ip_mreq)


def test_drop_membership(multicast_addr, vif_a1):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ip_mreq = data.IpMreq(multicast_addr, vif_a1["address"])
    sockopts.add_membership(sock, ip_mreq)
    sockopts.drop_membership(sock, ip_mreq)


def test_drop_membership_error(multicast_addr, vif_a1):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ip_mreq = data.IpMreq(multicast_addr, vif_a1["address"])
    with pytest.raises(OSError):
        sockopts.drop_membership(sock, ip_mreq)


def test_ttl():
    pass # TODO


def test_loop():
    pass # TODO


def test_interface():
    pass # TODO

