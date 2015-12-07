import unittest
from examples.gnr.renderingenvironment import BlenderEnvironment


class BlenderEnvTest(unittest.TestCase):
    def test_blender(self):
        env = BlenderEnvironment()
        assert bool(env.supported()) == bool(env.check_software())
