import os

import pytest

import networks

CLONE_NEWNET = 0x40000000  # The namespace type for network namespaces


def _require_root():
    # These tests create network namespaces and call setns(), which require privileges.
    # Skip when running unprivileged instead of erroring during fixture setup.
    if os.geteuid() != 0:
        pytest.skip("tests require root privileges (network namespaces)")


@pytest.fixture(scope="session", autouse=True)
def basic_network_namespace():
    _require_root()
    with networks.BasicNamespace() as ns:
        ns.summary()
        yield ns


@pytest.fixture(scope="session", autouse=True)
def network_namespace(basic_network_namespace):
    _require_root()
    networks.setns(basic_network_namespace.file())
    yield
    networks.setns("/proc/1/ns/net")
