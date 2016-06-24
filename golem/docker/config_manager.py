from contextlib import contextmanager

from golem.docker.task_thread import DockerTaskThread

__all__ = ['DockerConfigManager']

DEFAULT_HOST_CONFIG = dict(
    # privileged=False,
    # mount the container's root filesystem as read only
    read_only=True,
    # ['bridge', 'none', 'container:<name|id>', 'host']
    network_mode='none',
    dns=[],
    dns_search=[],
    cap_drop=['setgid', 'setuid', 'setpcap', 'setfcap',
              'net_admin', 'net_bind_service', 'net_raw',
              'mknod', 'audit_control', 'audit_write',
              'mac_admin', 'mac_override',
              'sys_chroot', 'sys_admin', 'sys_boot',
              'sys_module', 'sys_nice', 'sys_pacct',
              'sys_rawio', 'sys_resource', 'sys_time',
              'sys_tty_config']
)


class DockerConfigManager(object):

    container_host_config = dict(DEFAULT_HOST_CONFIG)

    def build_config(self, config_desc):
        host_config = dict()

        if config_desc:
            num_cores = config_desc.num_cores
            max_memory_size = config_desc.max_memory_size
            max_resource_size = config_desc.max_resource_size

            with self._try():
                cores = [str(c) for c in range(0, int(num_cores))]
                host_config['cpuset'] = ','.join(cores)

            with self._try():
                host_config['mem_limit'] = int(max_memory_size) * 1000

        self.container_host_config.update(host_config)
        DockerTaskThread.container_host_config = self.container_host_config

    @contextmanager
    def _try(self):
        try:
            yield
        except:
            pass
