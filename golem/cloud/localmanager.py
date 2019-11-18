from pathlib import Path
import logging

from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.resource.dirmanager import DirManager
from golem.task.envmanager import EnvironmentManager
from golem_task_api.envs import DOCKER_CPU_ENV_ID


logger = logging.getLogger(__name__)


class LocalContainerManager:
    DEFAULT_ENVIRONMENT = DOCKER_CPU_ENV_ID

    def __init__(self,
                 config_desc: ClientConfigDescriptor,
                 env_manager: EnvironmentManager,
                 root_path: Path):
        self.config_desc = config_desc
        self.env_manager = env_manager
        self.dir_manager = DirManager(root_path)
        self._environment = self.DEFAULT_ENVIRONMENT
        self._containers = []
        self._parse_config()

    @property
    def environment(self):
        return self.env_manager.environment(self._environment)

    def _parse_config(self):
        print(self.config_desc)
        print(self.dir_manager)
        print(dir(self.dir_manager))

    def run_local_containers(self):

        pass
        # self.environment.run_local_container(image, tag, extra_options)
