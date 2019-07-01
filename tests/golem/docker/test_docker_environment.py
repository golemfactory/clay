from enforce.exceptions import RuntimeTypeError

from apps.blender.blenderenvironment import BlenderEnvironment
from golem.docker.environment import DockerEnvironment
from golem.docker.image import DockerImage
from golem.tools.ci import ci_skip

from .test_docker_image import DockerTestCase


class DockerEnvironmentMock(DockerEnvironment):
    DOCKER_IMAGE = ""
    DOCKER_TAG = ""
    ENV_ID = ""
    SHORT_DESCRIPTION = ""


@ci_skip
class TestDockerEnvironment(DockerTestCase):
    def test_docker_environment(self):
        with self.assertRaises(TypeError):
            DockerEnvironment(None)

        with self.assertRaises(RuntimeTypeError):
            DockerEnvironmentMock(additional_images=["aaa"])

        de = DockerEnvironmentMock(additional_images=[
            DockerImage("golemfactory/blender", tag="1.10")])
        self.assertTrue(de.check_support())
        self.assertTrue(de.check_docker_images())

    def test_blender_docker_env(self):
        env = BlenderEnvironment()
        self.assertTrue(all(isinstance(img, DockerImage)
                            for img in env.docker_images))

        image_available = any(img.is_available() for img in env.docker_images)
        self.assertEqual(image_available, env.check_support().is_ok())
