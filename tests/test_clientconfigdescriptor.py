from unittest import TestCase
from golem.clientconfigdescriptor import ClientConfigDescriptor, ConfigApprover


class TestClientConfigDescriptor(TestCase):

    def test_init(self):
        ccd = ClientConfigDescriptor()
        assert isinstance(ccd, ClientConfigDescriptor)


class TestConfigApprover(TestCase):

    def test_approve(self):
        config = ClientConfigDescriptor()
        config.num_cores = '1'
        config.computing_trust = '1'

        approved_config = ConfigApprover(config).approve()

        assert isinstance(approved_config.num_cores, int)
        assert approved_config.num_cores == 1

        assert isinstance(approved_config.computing_trust, float)
        assert approved_config.computing_trust == 1.0
