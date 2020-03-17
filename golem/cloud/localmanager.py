from pathlib import Path
import logging
from copy import deepcopy
import time
import os
import sys

from twisted.internet.defer import inlineCallbacks

from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.resource.dirmanager import DirManager
from golem.task.envmanager import EnvironmentManager
from golem_task_api.envs import DOCKER_CPU_ENV_ID
from golem.envs.docker import DockerRuntimePayload
from golem.core.common import is_windows

from .config import load_config, get_config_path
from .schema.config import CloudConfigSchema

logger = logging.getLogger(__name__)

CONTAINER_RUN_DELAY = 5


class LocalContainerManager:
    DEFAULT_ENVIRONMENT = DOCKER_CPU_ENV_ID

    def __init__(self,
                 config_desc: ClientConfigDescriptor,
                 env_manager: EnvironmentManager,
                 root_path: Path):
        logger.warn('Enabling Golem Cloud LocalContainerManager')
        self.config_desc = config_desc
        self.env_manager = env_manager
        self.dir_manager = DirManager(root_path)
        self._environment = self.DEFAULT_ENVIRONMENT
        self._containers = {}
        self._deferreds = {}
        self.cloud_config = None
        self._parse_config()

    def __del__(self):
        self.quit()

    @inlineCallbacks
    def quit(self):
        logger.info('Golem Cloud is stopping local containers...')
        for container_name, container_runtime in self._containers.items():
            container_status = self.get_status(container_name)
            logger.info(
                f'Container: {container_name} status: {container_status}')
            yield container_runtime.stop()
            container_status = self.get_status(container_name)
            logger.info(
                f'Container: {container_name} status: {container_status}')
        self._containers = {}
        self._deferreds = {}

    @property
    def environment(self):
        return self.env_manager.environment(DOCKER_CPU_ENV_ID)

    def _parse_config(self):
        if self.config_desc.cloud_config:
            config_path = Path(self.config_desc.cloud_config)
        else:
            config_path = get_config_path()
        if not config_path.exists():
            logger.warning(
                f'Cloud configuration "{config_path}" does not exist.')
            return
        try:
            logger.info('Loading Golem Cloud configuration.')
            self.cloud_config = load_config(config_path,
                                            schema_class=CloudConfigSchema)
            logger.info('Cloud configuration loaded.')
        except Exception as e:
            import traceback
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback)
            logger.error(f'Cloud configuration FAILED: {e}')
            return

    def get_status(self, name):
        if name not in self._containers:
            return None
        runtime = self._containers.get(name)
        return runtime.status()

    def prepare_local_container(self, image, tag, extra_options=None):
        if not extra_options:
            extra_options = {}
        docker_env = extra_options.pop('env') if 'env' in extra_options \
            else {}

        payload = DockerRuntimePayload(
            image=image,
            tag=tag,
            user=None if is_windows() else str(os.getuid()),
            env=docker_env,
            **extra_options
        )
        return self.environment.runtime(payload)

    def run_local_containers(self):
        if not self.cloud_config:
            return None
        while self.environment.status() == 'DISABLED':
            logger.warning(self.environment.status())
            time.sleep(1)
        logger.info('Golem Cloud is starting local containers...')
        for container_desc in self.cloud_config.containers:
            name = container_desc['name']
            image = container_desc['container']['image']
            tag = container_desc['container']['tag']
            extra_options = deepcopy(container_desc['container'])
            del(extra_options['image'])
            del(extra_options['tag'])
            logger.info(
                f'Golem Cloud is starting container: {name} ({image}:{tag})')
            runtime = self.prepare_local_container(image, tag, extra_options)
            self._containers[name] = runtime
            self._deferreds[name] = self.environment.run_local_runtime(runtime)
            time.sleep(CONTAINER_RUN_DELAY)
