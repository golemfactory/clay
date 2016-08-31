import logging

import psutil
from contextlib import contextmanager

from golem.docker.task_thread import DockerTaskThread

__all__ = ['DockerConfigManager']
logger = logging.getLogger(__name__)

DEFAULT_HOST_CONFIG = dict(
    privileged=False,
    # mount the container's root filesystem as read only
    read_only=True,
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
        # Note that the number of cores is based on
        # CPU affinity set for Golem's process
        try:
            process = psutil.Process()
            self.cpu_cores = process.cpu_affinity()
        except Exception as exc:
            logger.error("Couldn't read CPU affinity: {}".format(exc))
            self.cpu_cores = None

    def build_config(self, config_desc):
        host_config = dict()

        if config_desc:
            num_cores = config_desc.num_cores
            max_memory_size = config_desc.max_memory_size
            max_resource_size = config_desc.max_resource_size

            with self._try():
                max_cpus = min(len(self.cpu_cores), int(num_cores) or 1)
                cpu_set = [str(c) for c in self.cpu_cores[:max_cpus]]
                host_config['cpuset'] = ','.join(cpu_set)

            with self._try():
                host_config['mem_limit'] = int(max_memory_size) * 1000

        self.container_host_config.update(host_config)

    @classmethod
    def install(cls, *args, **kwargs):
        docker_manager = cls(*args, **kwargs)
        DockerTaskThread.docker_manager = docker_manager
        return docker_manager

    @contextmanager
    def _try(self):
        try:
            yield
        except Exception:
            pass
