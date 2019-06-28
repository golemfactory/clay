from golem.docker.environment import DockerEnvironment
from golem.docker.image import DockerImage


class ffmpegEnvironment(DockerEnvironment):
    DOCKER_IMAGE = 'golemfactory/ffmpeg-experimental'
    DOCKER_TAG = '0.96.5'
    ENV_ID = 'FFMPEG'
    SHORT_DESCRIPTION = ''

    def __init__(self, binds: list = None):
        super().__init__(additional_images=[DockerImage(
            repository=self.DOCKER_IMAGE,
            tag=self.DOCKER_TAG
        )])
        self.binds = binds or []

    def get_container_config(self):
        d = super(ffmpegEnvironment, self).get_container_config()
        d['binds'] = self.binds
        return d
