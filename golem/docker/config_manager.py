from contextlib import contextmanager

__all__ = ['DockerConfigManager']


class DockerConfigManager(object):
    def __init__(self):
        self.container_create_config = None
        self.container_run_config = None

    def build_config(self, config_desc):
        run_config = dict()
        create_config = dict()

        if config_desc:
            num_cores = config_desc.num_cores
            max_memory_size = config_desc.max_memory_size
            max_resource_size = config_desc.max_resource_size

            with self._try():
                cores = [str(c) for c in range(0, int(num_cores))]
                run_config['cpuset'] = ','.join(cores)

            with self._try():
                run_config['mem_limit'] = int(max_memory_size) or None

        self.container_run_config = run_config
        self.container_create_config = self.container_run_config

    @contextmanager
    def _try(self):
        try:
            yield
        except:
            pass
