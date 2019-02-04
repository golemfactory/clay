from apps.transcoding.ffmpeg.environment import ffmpegEnvironment
from golem.docker.image import DockerImage
from golem.tools.ci import ci_skip
from tests.golem.docker.test_docker_image import DockerTestCase


@ci_skip
class TestffmpegEnvironment(DockerTestCase):
    def test_ffmpeg_env(self):
        env = ffmpegEnvironment()
        self.assertTrue(all(isinstance(img, DockerImage)
                            for img in env.docker_images))

        image_available = any(img.is_available() for img in env.docker_images)
        self.assertEqual(image_available, env.check_support().is_ok())
