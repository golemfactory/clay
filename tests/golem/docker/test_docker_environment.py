import unittest

from gnr.docker_environments import BlenderDockerEnvironment
from golem.task.docker.image import DockerImage


class TestDockerEnvironment(unittest.TestCase):

    def test_blender_docker_env(self):
        env = BlenderDockerEnvironment()
        self.assertTrue(all(isinstance(img, DockerImage)
                            for img in env.docker_images))

        image_available = any(img.is_available() for img in env.docker_images)
        self.assertEqual(image_available, env.supported())
