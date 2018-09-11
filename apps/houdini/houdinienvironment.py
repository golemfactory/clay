from os import path

from golem.core.common import get_golem_path
from golem.docker.environment import DockerEnvironment


class HoudiniEnvironment(DockerEnvironment):
    DOCKER_IMAGE = "golemfactory/houdini"
    DOCKER_TAG = "0.5"
    ENV_ID = "HOUDINI"
    APP_DIR = path.join(get_golem_path(), 'apps', 'houdini')
    SCRIPT_NAME = "docker_houdinitask.py"
    SHORT_DESCRIPTION = "Houdini (https://www.sidefx.com/)"
