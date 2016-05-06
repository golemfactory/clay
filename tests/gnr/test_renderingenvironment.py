import unittest

from golem.tools.testdirfixture import TestDirFixture

from gnr.renderingenvironment import BlenderEnvironment, LuxRenderEnvironment


class BlenderEnvTest(unittest.TestCase):
    def test_blender(self):
        env = BlenderEnvironment()
        assert bool(env.supported()) == bool(env.check_software())


class TestLuxRenderEnvironment(TestDirFixture):
    def test_lux(self):
        env = LuxRenderEnvironment()
        self.assertIsInstance(env, LuxRenderEnvironment)

