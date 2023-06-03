import pytest

import networks

CLONE_NEWNET = 0x40000000  # The namespace type for network namespaces



@pytest.fixture(scope='session', autouse=True)
def basic_network_namespace():
    with networks.BasicNamespace() as ns:
        ns.summary()
        yield ns


@pytest.fixture(scope='session', autouse=True)
def network_namespace(basic_network_namespace):
        networks.setns(basic_network_namespace.file())
        yield
        networks.setns('/proc/1/ns/net')
