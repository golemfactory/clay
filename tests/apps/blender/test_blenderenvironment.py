import unittest

from golem.clientconfigdescriptor import ClientConfigDescriptor

from apps.blender.blenderenvironment import BlenderEnvironment


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

