from os import path

from golem.core.common import get_golem_path
from golem.docker.environment import DockerEnvironment


class UpackTaskEnvironment(DockerEnvironment):
    DOCKER_IMAGE = "golemfactory/upack"
    DOCKER_TAG = "1.2"
    ENV_ID = "Upack"
    APP_DIR = path.join(get_golem_path(), 'apps', 'upack')
    SCRIPT_NAME = "docker_upacktask.py"
    SHORT_DESCRIPTION = "Upack task"
