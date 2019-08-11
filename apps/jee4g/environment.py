from golem.docker.environment import DockerEnvironment


class Jee4gTaskEnvironment(DockerEnvironment):
    DOCKER_IMAGE = "golemfactory/jee4g"
    DOCKER_TAG = "latest"
    ENV_ID = "JEE4G"
    SHORT_DESCRIPTION = "JEE4G container"
