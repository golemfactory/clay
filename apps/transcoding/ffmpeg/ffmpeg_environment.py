from golem.docker.environment import DockerEnvironment


class ffmpegEnvironment(DockerEnvironment):
    DOCKER_IMAGE = 'golemfactory/ffmpeg:0.2'
