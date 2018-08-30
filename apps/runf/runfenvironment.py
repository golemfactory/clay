from os import path

from golem.core.common import get_golem_path
from golem.docker.environment import DockerEnvironment


class RunFEnvironment(DockerEnvironment):
    DOCKER_IMAGE = "jacekjacekjacekg/runf"
    DOCKER_TAG = "latest"
    ENV_ID = "RUNF"
    APP_DIR = path.join(get_golem_path(), 'apps', 'runf')
    SCRIPT_NAME = "docker_runf.py"
    SHORT_DESCRIPTION = "Running arbitrary python code and returning result"
