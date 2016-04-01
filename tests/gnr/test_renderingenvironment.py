import unittest
from gnr.docker_environments import BlenderEnvironment


class BlenderEnvTest(unittest.TestCase):
    def test_blender(self):
        env = BlenderEnvironment()
        assert bool(env.supported()) == bool(env.check_software())
