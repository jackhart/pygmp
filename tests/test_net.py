import pytest

from pygmp.kernel import net


@pytest.fixture
def igmp_control_msg_bytes():
    return  b'E\x00\x00\x1c\x00\x00@\x00\x01\x00\x00\x00\n\x00\x00\x01\xef\x00\x00\x04\x01\x00\x00\x00\x00\x00\x00\x00'


@pytest.fixture
def igmp_ip_packet():
    return b'F\xc0\x00 \x00\x00@\x00\x01\x02\xeb\x14\n\x00\x00\x01\xef\x00\x00\x02\x94\x04\x00\x00\x16\x00\xfa\xfc\xef\x00\x00\x02'


def test_parse_igmp_control(igmp_control_msg_bytes):
    print(net.parse_igmp_control(igmp_control_msg_bytes))


def test_parse_ip_header(igmp_control_msg_bytes):
    # TODO - parameterize
    print(net.parse_ip_header(igmp_control_msg_bytes))


def test_parse_igmp(igmp_ip_packet):
    print(net.parse_igmp(igmp_ip_packet[24:]))


def test_network_interfaces():
    print(net.network_interfaces()) # TODO

