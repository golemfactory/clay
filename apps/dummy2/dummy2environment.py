from os import path

from golem.core.common import get_golem_path
from golem.docker.environment import DockerEnvironment


class Dummy2TaskEnvironment(DockerEnvironment):
    DOCKER_IMAGE = "golemfactory/base"
    DOCKER_TAG = "1.2"
    ENV_ID = "DUMMY2PW"
    APP_DIR = path.join(get_golem_path(), 'apps', 'dummy2')
    SCRIPT_NAME = "docker_dummy2task.py"
    SHORT_DESCRIPTION = "Dummy2 task (distributed password guessing"
