import logging
from contextlib import contextmanager

from golem.core.hardware import cpu_cores_available
from golem.docker.task_thread import DockerTaskThread

__all__ = ['DockerConfigManager']
logger = logging.getLogger(__name__)

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


class DockerConfigManager(object):

    def __init__(self):
        self.container_host_config = dict(DEFAULT_HOST_CONFIG)

    def build_config(self, config_desc):
        host_config = dict()

        if config_desc:
            num_cores = config_desc.num_cores
            max_memory_size = config_desc.max_memory_size

            with self._try():
                cpu_cores = cpu_cores_available()
                max_cpus = min(len(cpu_cores), max(int(num_cores), 1))
                cpu_set = [str(c) for c in cpu_cores[:max_cpus]]
                host_config['cpuset'] = ','.join(cpu_set)

            with self._try():
                host_config['mem_limit'] = int(max_memory_size) * 1000

        self.container_host_config.update(host_config)

    @classmethod
    def install(cls, *args, **kwargs):
        if not DockerTaskThread.docker_manager:
            docker_manager = cls(*args, **kwargs)
            DockerTaskThread.docker_manager = docker_manager
        return DockerTaskThread.docker_manager

    @contextmanager
    def _try(self):
        try:
            yield
        except Exception:
            pass
