from unittest import TestCase
from golem.clientconfigdescriptor import ClientConfigDescriptor, ConfigApprover
from golem.core.variables import KEY_DIFFICULTY


class TestClientConfigDescriptor(TestCase):

    def test_init(self):
        ccd = ClientConfigDescriptor()
        assert isinstance(ccd, ClientConfigDescriptor)
        u = int(ccd.use_distributed_resource_management)
        assert u in [0, 1]


class TestConfigApprover(TestCase):

    def test_approve(self):
        config = ClientConfigDescriptor()
        config.num_cores = '1'
        config.computing_trust = '1'
        config.key_difficulty = '0'

        approved_config = ConfigApprover(config).approve()

        assert isinstance(approved_config.num_cores, int)
        assert approved_config.num_cores == 1

        assert isinstance(approved_config.computing_trust, float)
        assert approved_config.computing_trust == 1.0

        assert isinstance(approved_config.key_difficulty, int)
        assert approved_config.key_difficulty == KEY_DIFFICULTY

    def test_max_value_error(self):
        key_error_var = 1
        assert ConfigApprover._max_value(key_error_var, 'does_not_exist') is \
            key_error_var
