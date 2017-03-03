import unittest
from os import path

from apps.lux.luxenvironment import LuxRenderEnvironment
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.tools.ci import ci_skip


@ci_skip
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

    def test_main_program_file(self):
        assert path.isfile(LuxRenderEnvironment().main_program_file)
