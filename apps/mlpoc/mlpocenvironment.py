from os import path

from golem.core.common import get_golem_path
from golem.docker.environment import DockerEnvironment


class MLPOCTorchEnvironment(DockerEnvironment):
    DOCKER_IMAGE = "jacekjacekjacekg/mlbase"
    DOCKER_TAG = "latest"
    ENV_ID = "MLPOC"
    APP_DIR = path.join(get_golem_path(), 'apps', 'mlpoc')
    SCRIPT_NAME = "provider_main.py"
    SHORT_DESCRIPTION = "Provider-side and verificatoin enviromnent for MLPOC task used to run torch"

    def get_performance(self, cfg_desc):
        return cfg_desc.estimated_mlpoctask_performance


class MLPOCSpearmintEnvironment(DockerEnvironment):
    DOCKER_IMAGE = "jacekjacekjacekg/mlspearmint"
    DOCKER_TAG = "latest"
    ENV_ID = "MLPOC"
    APP_DIR = path.join(get_golem_path(), 'apps', 'mlpoc')
    SCRIPT_NAME = "docker_spearmint.py"
    SHORT_DESCRIPTION = "Requestor-side environment used to run Spearmint"

    def get_performance(self, _):
        return 0