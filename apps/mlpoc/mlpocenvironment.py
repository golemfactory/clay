from os import path

from golem.core.common import get_golem_path
from golem.docker.environment import DockerEnvironment


class MLPOCTaskEnvironment(DockerEnvironment):
    DOCKER_IMAGE = "golemfactory/mlpoc"
    DOCKER_TAG = "1.0"
    ENV_ID = "MLPOC"
    APP_DIR = path.join(get_golem_path(), 'apps', 'mlpoc')
    SCRIPT_NAME = "provider_main.py"
    SHORT_DESCRIPTION = "Example machine learning POC task, searching for " \
                        "best neural network hyperparameters using bayesian " \
                        "optimization"

    def get_performance(self, cfg_desc):
        return cfg_desc.estimated_mlpoctask_performance
