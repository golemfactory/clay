from unittest import TestCase
from golem.clientconfigdescriptor import ClientConfigDescriptor


class TestClientConfigDescriptor(TestCase):
    def test_init(self):
        ccd = ClientConfigDescriptor()
        assert isinstance(ccd, ClientConfigDescriptor)
        u = int(ccd.use_distributed_resource_management)
        assert u in [0, 1]
