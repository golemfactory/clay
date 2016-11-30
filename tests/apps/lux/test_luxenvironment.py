import unittest

from apps.lux.luxenvironment import LuxRenderEnvironment
from golem.clientconfigdescriptor import ClientConfigDescriptor


class TestLuxRenderEnvironment(unittest.TestCase):
    def test_lux(self):
        env = LuxRenderEnvironment()
        self.assertIsInstance(env, LuxRenderEnvironment)

    def test_get_performance(self):
        env = LuxRenderEnvironment()
        perf = 1234.5
        cfg_desc = ClientConfigDescriptor()
        cfg_desc.estimated_lux_performance = perf
        result = env.get_performance(cfg_desc)
        self.assertTrue(result == perf)
