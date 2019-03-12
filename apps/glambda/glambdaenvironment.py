from golem.docker.environment import DockerEnvironment


class GLambdaTaskEnvironment(DockerEnvironment):
    DOCKER_IMAGE = "golemfactory/glambda"
    DOCKER_TAG = "1.3"
    ENV_ID = "glambda"
    SHORT_DESCRIPTION = "GLambda PoC"
