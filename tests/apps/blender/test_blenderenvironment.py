import unittest
from os import path

from golem.clientconfigdescriptor import ClientConfigDescriptor

from apps.blender.blenderenvironment import BlenderEnvironment
from golem.tools.ci import ci_skip


@ci_skip
class BlenderEnvTest(unittest.TestCase):
    def test_blender(self):
        """Basic environment test."""
        env = BlenderEnvironment()
        self.assertTrue(env.supported())
        self.assertTrue(env.check_software())

    def test_get_performance(self):
        """Changing estimated performance in ClientConfigDescriptor."""
        env = BlenderEnvironment()
        fake_performance = 2345.2
        cfg_desc = ClientConfigDescriptor()
        cfg_desc.estimated_blender_performance = fake_performance
        result = env.get_performance(cfg_desc)
        self.assertEquals(result, fake_performance)

    def test_main_program_file(self):
        assert path.isfile(BlenderEnvironment().main_program_file)
