from gnr.docker_environments import BlenderDockerEnvironment
from golem.task.docker.image import DockerImage

from test_docker_image import DockerTestCase


class TestDockerEnvironment(DockerTestCase):

    def test_blender_docker_env(self):
        env = BlenderDockerEnvironment()
        self.assertTrue(all(isinstance(img, DockerImage)
                            for img in env.docker_images))

        image_available = any(img.is_available() for img in env.docker_images)
        self.assertEqual(image_available, env.supported())
