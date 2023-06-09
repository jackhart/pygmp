from enum import Enum
from ipaddress import IPv4Address, ip_address

import pytest

from pygmp import data


@pytest.fixture
def inaddr_str():
    return "10.10.0.1"


@pytest.fixture
def multicast_addr():
    return "239.0.0.4"


def test_ipmreq(inaddr_str, multicast_addr):
    ipmreq = data.IpMreq(multicast_addr, inaddr_str)
    assert isinstance(ipmreq.multiaddr, (IPv4Address,))
    assert isinstance(ipmreq.interface, (IPv4Address,))
    assert str(ipmreq.multiaddr) == multicast_addr
    assert str(ipmreq.interface) == inaddr_str
    assert ipmreq.multiaddr.is_multicast


def test_ipmreq_from_ip_obj(inaddr_str, multicast_addr):
    ipmreq = data.IpMreq(ip_address(multicast_addr), ip_address(inaddr_str))
    assert isinstance(ipmreq.multiaddr, (IPv4Address,))
    assert str(ipmreq.multiaddr) == multicast_addr
    assert str(ipmreq.interface) == inaddr_str
    assert ipmreq.multiaddr.is_multicast


def test_vifreq():
    vif_req = data.VifReq(1, 2, 3, 4, 5)
    assert vif_req.vifi == 1
    assert vif_req.icount == 2
    assert vif_req.ocount == 3
    assert vif_req.ibytes == 4
    assert vif_req.obytes == 5


def test_vifctl(inaddr_str, multicast_addr):
    vif_ctl = data.VifCtl(1, inaddr_str, multicast_addr, 2, 0)
    assert isinstance(vif_ctl.lcl_addr, (IPv4Address,))
    assert isinstance(vif_ctl.rmt_addr, (IPv4Address,))
    assert vif_ctl.vifi == 1
    assert vif_ctl.threshold == 2
    assert vif_ctl.rate_limit == 0
    assert str(vif_ctl.lcl_addr) == inaddr_str
    assert str(vif_ctl.rmt_addr) == multicast_addr
    assert vif_ctl.rmt_addr.is_multicast


def test_vifctl_from_ip_obj(inaddr_str, multicast_addr):
    vif_ctl = data.VifCtl(1, IPv4Address(inaddr_str), IPv4Address(multicast_addr), 2, 0)
    assert isinstance(vif_ctl.lcl_addr, (IPv4Address,))
    assert isinstance(vif_ctl.rmt_addr, (IPv4Address,))
    assert vif_ctl.vifi == 1
    assert vif_ctl.threshold == 2
    assert vif_ctl.rate_limit == 0
    assert str(vif_ctl.lcl_addr) == inaddr_str
    assert str(vif_ctl.rmt_addr) == multicast_addr
    assert vif_ctl.rmt_addr.is_multicast


def test_vifctl_with_defaults(inaddr_str):
    vif_ctl = data.VifCtl(4, inaddr_str)
    assert isinstance(vif_ctl.lcl_addr, (IPv4Address,))
    assert str(vif_ctl.lcl_addr) == inaddr_str
    assert vif_ctl.vifi == 4
    assert vif_ctl.threshold == data.VifCtl.threshold
    assert vif_ctl.rate_limit == data.VifCtl.rate_limit


def test_vifctl_index(multicast_addr):
    vif_ctl = data.VifCtl(1, 2, multicast_addr, 2, 0)
    assert isinstance(vif_ctl.lcl_addr, (int,))
    assert vif_ctl.vifi == 1
    assert vif_ctl.lcl_addr == 2


def test_mfctl(inaddr_str, multicast_addr):
    mfc_ctl = data.MfcCtl(inaddr_str, multicast_addr, 3, [1] * 4, 0)
    assert isinstance(mfc_ctl.origin, (IPv4Address,))
    assert isinstance(mfc_ctl.mcastgroup, (IPv4Address,))
    assert str(mfc_ctl.origin) == inaddr_str
    assert str(mfc_ctl.mcastgroup) == multicast_addr
    assert mfc_ctl.parent == 3
    assert len(mfc_ctl.ttls) == 4
    assert all(i == 1 for i in mfc_ctl.ttls)
    assert mfc_ctl.expire == 0


def test_interface():
    intf = data.Interface("eth0", 0, data.InterfaceFlags.UP | data.InterfaceFlags.MULTICAST, {"0.0.0.0", "192.168.2.2"})
    assert len(intf.flags) == 2
    assert len(intf.flags & {data.InterfaceFlags.UP, data.InterfaceFlags.MULTICAST}) == 2
    assert len(intf.addresses) == 2


def test_interface_equivalence():
    intf1 = data.Interface("eth0", 0, data.InterfaceFlags.UP | data.InterfaceFlags.MULTICAST, {"0.0.0.0", "192.168.2.2"})
    intf2 = data.Interface("eth0", 0, data.InterfaceFlags.UP | data.InterfaceFlags.MULTICAST, {"0.0.0.0", "192.168.2.2"})
    intf3 = data.Interface("eth0", 0, data.InterfaceFlags.UP | data.InterfaceFlags.MULTICAST, {"0.0.0.0", "10.0.0.2"})

    assert intf1 == intf2
    assert intf1 != intf3



def test_igmp_control(inaddr_str, multicast_addr):
    igmp_control = data.IGMPControl(data.ControlMsgType.IGMPMSG_NOCACHE, 0, 1, inaddr_str, multicast_addr)
    assert igmp_control.msgtype == data.ControlMsgType.IGMPMSG_NOCACHE
    assert isinstance(igmp_control.msgtype, Enum)

    igmp_control = data.IGMPControl(int(data.ControlMsgType.IGMPMSG_NOCACHE), 0, 1, inaddr_str, multicast_addr)
    assert igmp_control.msgtype == data.ControlMsgType.IGMPMSG_NOCACHE
    assert isinstance(igmp_control.msgtype, Enum)


def test_ip_header(inaddr_str, multicast_addr):
    header = data.IPHeader(data.IPVersion.IPv4, 0, 0, 20, 0, 0, 2, data.IPProtocol.PIM, 22, inaddr_str, multicast_addr)
    assert isinstance(header.version, Enum)
    assert isinstance(header.protocol, Enum)

    header = data.IPHeader(4, 0, 0, 20, 0, 0, 2, 103, 22, inaddr_str, multicast_addr)
    assert isinstance(header.version, Enum)
    assert isinstance(header.protocol, Enum)


def test_igmp(multicast_addr):
    msg = data.IGMP(data.IGMPType.MEMBERSHIP_QUERY, 0, 0, multicast_addr)
    assert isinstance(msg.type, Enum)

    msg = data.IGMP(22, 0, 0, multicast_addr)
    assert isinstance(msg.type, Enum)


def test_igmpv3_membership_report_init():
    report = data.IGMPv3MembershipReport(
        type=data.IGMPType.V3_MEMBERSHIP_REPORT,
        checksum=0,
        num_records=1,
        grec_list=[data.IGMPv3Record(type=data.IGMPv3RecordType.MODE_IS_EXCLUDE,
                                     auxwords=0,
                                     nsrcs=0,
                                     mca=IPv4Address('239.1.1.1'),
                                     src_list=[])])


def test_igmpv3_membership_report_raw_init():
    raw_report = {
        "type": 0x22,
        "checksum":0,
        "num_records": 1,
        "grec_list": [{
            "type": 2,
            "auxwords": 0,
            "nsrcs": 0,
            "mca": "239.1.1.1",
            "src_list": []
        }]
    }

    report = data.IGMPv3MembershipReport(**raw_report)
    assert report.type == data.IGMPType.V3_MEMBERSHIP_REPORT
    assert isinstance(report.type, Enum)
    assert len(report.grec_list) == 1
    assert report.grec_list[0].type == data.IGMPv3RecordType.MODE_IS_EXCLUDE
    assert isinstance(report.grec_list[0].type, Enum)
    assert len(report.grec_list[0].src_list) == 0
    assert isinstance(report.grec_list[0].mca, IPv4Address)



