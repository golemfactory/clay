from os import path

from golem.core.common import get_golem_path
from golem.docker.environment import DockerEnvironment

class GLambdaTaskEnvironment(DockerEnvironment):
    DOCKER_IMAGE = "golemfactory/glambda"
    DOCKER_TAG = "1.1"
    ENV_ID = "glambda"
    SHORT_DESCRIPTION = "GLambda PoC"
