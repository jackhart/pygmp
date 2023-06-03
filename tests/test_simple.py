import pytest

from pygmp import kernel
from pygmp.daemons import config, simple


@pytest.fixture
def igmp_sock():
    with kernel.igmp_socket() as sock:
        yield sock


@pytest.fixture
def example_config():  # FIXME
    return config.load_config("/home/jack/Documents/projects/pygmp/tests/simple.ini")


@pytest.fixture
def cleaned_igmp_sock(igmp_sock):
    kernel.disable_pim(igmp_sock)
    kernel.flush(igmp_sock)
    kernel.enable_mrt(igmp_sock)

    yield igmp_sock
    kernel.flush(igmp_sock)


@pytest.fixture
def vif_manager(cleaned_igmp_sock, example_config):
    return simple.VifManager(cleaned_igmp_sock, example_config.phyint)


@pytest.fixture
def empty_vif_manager(cleaned_igmp_sock):
    return simple.VifManager(cleaned_igmp_sock)


@pytest.fixture
def mfc_manager(cleaned_igmp_sock, vif_manager, example_config):
    return simple.MfcManager(cleaned_igmp_sock, vif_manager, example_config.mroute)


def test_vifmanager_init(vif_manager):
    vifs = vif_manager.vifs()
    assert len(vifs) == 3
    assert vifs.keys() == {"a1", "a2", "a3"}


def test_vifmanager_add(empty_vif_manager, example_config):
    for interf in example_config.phyint:
        empty_vif_manager.add(interf)

    assert len(empty_vif_manager.vifs()) == 3
    assert empty_vif_manager.vifs().keys() == {"a1", "a2", "a3"}


def test_vifmanager_add_duplicate(vif_manager, example_config):
    with pytest.raises(ValueError):
        vif_manager.add(example_config.phyint[0])


def test_vifmanager_vifi(vif_manager):
    assert vif_manager.vifi("a1") == 0
    assert vif_manager.vifi("a2") == 1
    assert vif_manager.vifi("a3") == 2
    with pytest.raises(ValueError):
        vif_manager.vifi("a4")


def test_mfcmanager_init(mfc_manager):
    assert len(mfc_manager.static_mfc()) == 1
    assert len(mfc_manager.dynamic_mfc()) == 1


def test_mfcmanager_add_duplicate(mfc_manager, example_config):
    mfc_manager.add(example_config.mroute[0])
    mfc_manager.add(example_config.mroute[1])
    assert len(next(iter(mfc_manager.static_mfc().values()))) == 1
    assert len(next(iter(mfc_manager.dynamic_mfc().values()))) == 1


def test_mfcmanager_remove(mfc_manager, example_config):
    mfc_manager.remove(example_config.mroute[0])
    mfc_manager.remove(example_config.mroute[1])
    assert len(mfc_manager.static_mfc()) == 0
    assert len(mfc_manager.dynamic_mfc()) == 0
