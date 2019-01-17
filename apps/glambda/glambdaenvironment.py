from os import path

from golem.core.common import get_golem_path
from golem.docker.environment import DockerEnvironment

class GLambdaTaskEnvironment(DockerEnvironment):
    DOCKER_IMAGE = "golemfactory/glambda"
    DOCKER_TAG = "1.0"
    ENV_ID = "glambda"
    APP_DIR = path.join(get_golem_path(), 'apps', 'glambda')
    SCRIPT_NAME = "docker_glambdatask.py"
    SHORT_DESCRIPTION = "GLambda PoC"
