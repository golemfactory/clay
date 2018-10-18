from os import path

from golem.core.common import get_golem_path
from golem.docker.environment import DockerEnvironment

class FireworksTaskEnvironment(DockerEnvironment):
    DOCKER_IMAGE = "golemfactory/fireworks"
    DOCKER_TAG = "1.0"
    ENV_ID = "fireworks"
    APP_DIR = path.join(get_golem_path(), 'apps', 'fireworks')
    SCRIPT_NAME = "docker_fireworkstask.py"
    SHORT_DESCRIPTION = "Fireworks PoC"
