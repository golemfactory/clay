import unittest

from golem.environments.environment import Environment
from golem.clientconfigdescriptor import ClientConfigDescriptor


class EnvTest(unittest.TestCase):

    def test_get_performance(self):
        env = Environment()
        perf = 6666.6
        cfg_desc = ClientConfigDescriptor()
        cfg_desc.estimated_performance = perf
        result = env.get_performance(cfg_desc)
        self.assertTrue(result == perf)
