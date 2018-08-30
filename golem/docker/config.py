import logging
import os
from typing import Callable, Dict, Any, Optional

from golem.core.common import get_golem_path
from golem.core.hardware import cpu_cores_available
from golem.docker.task_thread import DockerTaskThread

logger = logging.getLogger(__name__)

ROOT_DIR = get_golem_path()
APPS_DIR = os.path.join(ROOT_DIR, 'apps')
IMAGES_INI = os.path.join(APPS_DIR, 'images.ini')

DOCKER_VM_NAME = 'golem'
DOCKER_VM_STATUS_RUNNING = 'Running'

DEFAULT_HOST_CONFIG = dict(
    privileged=False,
    # mount the container's root filesystem as read only
    # read_only=True,
    # ['bridge', 'none', 'container:<name|id>', 'host']
    network_mode='none',
    dns=[],
    dns_search=[],
    cap_drop=['setpcap', 'setfcap',
              'net_admin', 'net_bind_service', 'net_raw',
              'mknod', 'audit_control', 'audit_write',
              'mac_admin', 'mac_override',
              'sys_chroot', 'sys_admin', 'sys_boot',
              'sys_module', 'sys_nice', 'sys_pacct',
              'sys_resource', 'sys_time', 'sys_tty_config']
)

CONSTRAINT_KEYS = dict(
    mem='memory_size',
    cpu='cpu_count',
    cpu_cap='cpu_execution_cap'
)
MIN_CONSTRAINTS = dict(
    memory_size=1024,
    cpu_execution_cap=10,
    cpu_count=1
)
DEFAULTS = dict(
    memory_size=1024,
    cpu_execution_cap=100,
    cpu_count=1
)


GetConfigFunction = Callable[[], Dict[str, Any]]


class DockerConfigManager(object):

    def __init__(self):
        self.container_host_config = dict(DEFAULT_HOST_CONFIG)
        self.hypervisor: Optional['Hypervisor'] = None

    def build_config(self, config_desc) -> None:
        host_config = dict()

        if config_desc:
            num_cores = config_desc.num_cores
            max_memory_size = config_desc.max_memory_size

            try:
                cpu_cores = cpu_cores_available()
                max_cpus = min(len(cpu_cores), max(int(num_cores), 1))
                cpu_set = [str(c) for c in cpu_cores[:max_cpus]]
                host_config['cpuset'] = ','.join(cpu_set)
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning('Cannot set the CPU set: %r', exc)

            try:
                host_config['mem_limit'] = int(max_memory_size) * 1024
            except (TypeError, ValueError) as exc:
                logger.warning('Cannot set the memory limit: %r', exc)

        self.container_host_config.update(host_config)

    @classmethod
    def install(cls, *args, **kwargs):
        if not DockerTaskThread.docker_manager:
            docker_manager = cls(*args, **kwargs)
            DockerTaskThread.docker_manager = docker_manager
        return DockerTaskThread.docker_manager

    def quit(self) -> None:
        if self.hypervisor:
            self.hypervisor.quit()
