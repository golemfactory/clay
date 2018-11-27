from os import path

from golem.core.common import get_golem_path
from golem.docker.environment import DockerEnvironment


class DummyTaskEnvironment(DockerEnvironment):
    DOCKER_IMAGE = "golemfactory/base"
    DOCKER_TAG = "1.4"
    ENV_ID = "DUMMYPOW"
    APP_DIR = path.join(get_golem_path(), 'apps', 'dummy')
    SCRIPT_NAME = "docker_dummytask.py"
    SHORT_DESCRIPTION = "Dummy task (example app calculating proof-of-work " \
                        "hash)"
