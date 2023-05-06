import pytest
import socket

from pygmp import data, kernel, _kernel

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
def igmp_control_msg_bytes():
    return  b'E\x00\x00\x1c\x00\x00@\x00\x01\x00\x00\x00\n\x00\x00\x01\xef\x00\x00\x04\x01\x00\x00\x00\x00\x00\x00\x00'


@pytest.fixture
def igmp_ip_packet():
    return b'F\xc0\x00 \x00\x00@\x00\x01\x02\xeb\x14\n\x00\x00\x01\xef\x00\x00\x02\x94\x04\x00\x00\x16\x00\xfa\xfc\xef\x00\x00\x02'

@pytest.fixture(params=[
    (b'\x11\x00\x94\x04\xef\x00\x00\x01', data.IGMP(data.IGMPType.MEMBERSHIP_QUERY, 0, 37892, "239.0.0.1")),
    (b'\x12\x00\x94\x04\xef\x00\x00\x02', data.IGMP(data.IGMPType.V1_MEMBERSHIP_REPORT, 0, 37892, "239.0.0.2")),
    (b'\x16\x00\x3e\xd4\xef\x00\x00\x03', data.IGMP(data.IGMPType.V2_MEMBERSHIP_REPORT, 0, 16084, "239.0.0.3")),
    (b'\x17\x00\x94\x04\xef\x00\x00\x04', data.IGMP(data.IGMPType.V2_LEAVE_GROUP, 0, 37892, "239.0.0.4"))])
def igmpv12_msg(request):
    return request.param


@pytest.fixture
def igmpv2_leave_bytes():
    return b'\x17\x00\x94\x04\xef\x00\x00\x04'


@pytest.fixture
def vif_a1():
    return {"name": "a1", "address": "10.0.0.1", "ifindx": 2}

@pytest.fixture
def vif_a2():
    return {"name": "a2", "address": "20.0.0.1", "ifindx": 3}


@pytest.fixture
def multicast_addr():
    return "239.0.0.4"


@pytest.fixture
def sock():
    with kernel.igmp_socket() as sock:
        yield sock

@pytest.fixture
def cleaned_sock(sock):
    kernel.disable_pim(sock)
    kernel.enable_mrt(sock)
    kernel.flush(sock)

    yield sock
    kernel.flush(sock)


def test_mrt_version(cleaned_sock):
    assert kernel.mrt_version(cleaned_sock) == hex(0x0305)


def test_enable_mrt_unclean(sock):
    kernel.enable_mrt(sock)


def test_enable_mrt(cleaned_sock):
    # it should be enabled already and throw this error.
    with pytest.raises(OSError):
        kernel.enable_mrt(cleaned_sock)


def test_disable_mrt_unclean(sock):
    with pytest.raises(OSError):
        kernel.disable_mrt(sock)


def test_disable_mrt(cleaned_sock):
    kernel.disable_mrt(cleaned_sock)
    kernel.enable_mrt(cleaned_sock)


def test_enable_pim(sock):
    # TODO - not clear how to validate this.
    kernel.enable_pim(sock)


def test_disable_pim(cleaned_sock):
    # TODO - not clear how to validate this.
    kernel.disable_pim(cleaned_sock)


def test_add_vif(cleaned_sock, vif_a1):
    vif_ctl = data.VifCtl(vifi=1, lcl_addr=vif_a1["address"])
    kernel.add_vif(cleaned_sock, vif_ctl)

    with pytest.raises(OSError):
        kernel.add_vif(cleaned_sock, vif_ctl)


def test_add_vif_by_index(cleaned_sock, vif_a1):
    vif_ctl = data.VifCtl(vifi=1, lcl_addr=int(vif_a1["ifindx"]))
    kernel.add_vif(cleaned_sock, vif_ctl)


def test_add_remove_vif(cleaned_sock, vif_a1, multicast_addr):
    vif_ctl = data.VifCtl(vifi=1, lcl_addr=vif_a1["address"])
    kernel.add_vif(cleaned_sock, vif_ctl)
    kernel.del_vif(cleaned_sock, vif_ctl)

    with pytest.raises(OSError):
        kernel.del_vif(cleaned_sock, vif_ctl)


def test_get_vif_counts(cleaned_sock, vif_a1):
    vif_ctl = data.VifCtl(vifi=1, lcl_addr=vif_a1["address"])
    kernel.add_vif(cleaned_sock, vif_ctl)

    vif_req = data.VifReq(1)
    vif_req_new = kernel.get_vif_counts(cleaned_sock, vif_req)
    assert vif_req_new.icount == 0
    assert vif_req_new.ocount == 0
    assert vif_req_new.ibytes == 0
    assert vif_req_new.obytes == 0


def test_get_mfc_counts(cleaned_sock, vif_a1, vif_a2, multicast_addr):
    vif_ctl = data.VifCtl(vifi=0, lcl_addr=vif_a1["address"])
    kernel.add_vif(cleaned_sock, vif_ctl)

    vif_ctl = data.VifCtl(vifi=1, lcl_addr=vif_a2["address"])
    kernel.add_vif(cleaned_sock, vif_ctl)

    mfc_ctl = data.MfcCtl(vif_a1["address"], multicast_addr, 1, [0, 1, 1])
    kernel.add_mfc(cleaned_sock, mfc_ctl)

    mfc_req = data.SGReq(vif_a1["address"], multicast_addr)
    mfc_req_new = kernel.get_mfc_counts(cleaned_sock, mfc_req)
    print(mfc_req_new)


def test_get_vif_counts_error(cleaned_sock):
    with pytest.raises(OSError):
        vif_req = data.VifReq(1)
        _ = kernel.get_vif_counts(cleaned_sock, vif_req)


def test_add_mfc(cleaned_sock, vif_a1, multicast_addr):
    # add VIF
    vif_ctl = data.VifCtl(vifi=1, lcl_addr=vif_a1["address"])
    kernel.add_vif(cleaned_sock, vif_ctl)

    # add route
    mfc_ctl = data.MfcCtl(vif_a1["address"], multicast_addr, 1, [0, 1])
    kernel.add_mfc(cleaned_sock, mfc_ctl)


def test_del_mfc(cleaned_sock, vif_a1, multicast_addr):
    # add VIF
    vif_ctl = data.VifCtl(vifi=1, lcl_addr=vif_a1["address"])
    kernel.add_vif(cleaned_sock, vif_ctl)

    # add route
    mfc_ctl = data.MfcCtl(vif_a1["address"], multicast_addr, 1, [0, 1])
    kernel.add_mfc(cleaned_sock, mfc_ctl)

    # delete route
    kernel.del_mfc(cleaned_sock, mfc_ctl)


def test_flush(cleaned_sock, vif_a1, multicast_addr):
    # add VIF
    vif_ctl = data.VifCtl(vifi=1, lcl_addr=vif_a1["address"])
    kernel.add_vif(cleaned_sock, vif_ctl)

    # add route
    mfc_ctl = data.MfcCtl(vif_a1["address"], multicast_addr, 1, [0, 1])
    kernel.add_mfc(cleaned_sock, mfc_ctl)

    # flush
    kernel.flush(cleaned_sock)

    # add VIF - won't throw error
    vif_ctl = data.VifCtl(vifi=1, lcl_addr=vif_a1["address"])
    kernel.add_vif(cleaned_sock, vif_ctl)


def test_add_membership(multicast_addr, vif_a1):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ip_mreq = data.IpMreq(multicast_addr, vif_a1["address"])
    kernel.add_membership(sock, ip_mreq)


def test_drop_membership(multicast_addr, vif_a1):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ip_mreq = data.IpMreq(multicast_addr, vif_a1["address"])
    kernel.add_membership(sock, ip_mreq)
    kernel.drop_membership(sock, ip_mreq)


def test_drop_membership_error(multicast_addr, vif_a1):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ip_mreq = data.IpMreq(multicast_addr, vif_a1["address"])
    with pytest.raises(OSError):
        kernel.drop_membership(sock, ip_mreq)


def test_ttl():
    pass # TODO


def test_loop():
    pass # TODO


def test_interface():
    pass # TODO


def test_parse_igmp_control(igmp_control_msg_bytes):
    print(kernel.parse_igmp_control(igmp_control_msg_bytes))


def test_parse_ip_header(igmp_control_msg_bytes):
    # TODO - parameterize
    print(kernel.parse_ip_header(igmp_control_msg_bytes))


def test_parse_igmp(igmpv12_msg):
    bytes_str, obj = igmpv12_msg
    igmp_packet = kernel.parse_igmp(bytes_str)
    assert igmp_packet == obj


def test_parse_igmpv3_query():
    igmpv3_query_message = b'\x11\x64\x00\x00\xef\x00\x00\x01\x00\x00\x00\x01\xc0\xa8\x01\x01'
    igmp_packet = _kernel.parse_igmp(igmpv3_query_message)
    print(igmp_packet)

    print(data.IGMPv3Query(**igmp_packet))


def test_parse_igmpv3_report():
    igmpv3_report = bytearray([
        0x22, 0x00, 0x00, 0x1c, # Type=0x22 (Membership Report), Reserved=0x00, Checksum=0x001c
        0x00, 0x00, 0x00, 0x01, # Reserved=0x0000, Number of Group Records (N)=0x0001 (1 record)
        0x03, 0x00, 0x00, 0x01, # Record Type=0x03, Auxiliary Data Length=0x00, Number of Sources (N)=0x0001 (1 source)
        0xef, 0x00, 0x00, 0x04, # Multicast Address=239.0.0.4
        0xc0, 0xa8, 0x01, 0x0a  # Source Address=192.168.1.10
    ])

    igmp_packet = _kernel.parse_igmp(bytes(igmpv3_report))
    print(igmp_packet)
    print(data.IGMPv3MembershipReport(**igmp_packet))


def test_network_interfaces():
    print(kernel.network_interfaces()) # TODO
