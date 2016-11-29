import unittest

from apps.blender.blenderenvironment import BlenderEnvironment
from apps.lux.luxenvironment import LuxRenderEnvironment
from golem.clientconfigdescriptor import ClientConfigDescriptor


class BlenderEnvTest(unittest.TestCase):

    def test_blender(self):
        env = BlenderEnvironment()
        assert bool(env.supported()) == bool(env.check_software())
        
    def test_get_performance(self):
        env = BlenderEnvironment()
        perf = 2345.2
        cfg_desc = ClientConfigDescriptor()
        cfg_desc.estimated_blender_performance = perf
        result = env.get_performance(cfg_desc)
        self.assertTrue(result == perf)
        

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
