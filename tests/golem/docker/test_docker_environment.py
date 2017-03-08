from apps.blender.blenderenvironment import BlenderEnvironment
from golem.docker.environment import DockerEnvironment
from golem.docker.image import DockerImage
from golem.tools.ci import ci_skip

from test_docker_image import DockerTestCase


@ci_skip
class TestDockerEnvironment(DockerTestCase):
    def test_docker_environment(self):
        with self.assertRaises(AttributeError):
            DockerEnvironment(None)
        de = DockerEnvironment([DockerImage("golemfactory/blender", tag="1.3")])
        self.assertTrue(de.supported())
        self.assertTrue(
            de.description().startswith('Default environment for generic tasks without any additional requirements.'))
        self.assertTrue(de.check_docker_images())

    def test_blender_docker_env(self):
        env = BlenderEnvironment()
        self.assertTrue(all(isinstance(img, DockerImage)
                            for img in env.docker_images))

        image_available = any(img.is_available() for img in env.docker_images)
        self.assertEqual(image_available, env.supported())
