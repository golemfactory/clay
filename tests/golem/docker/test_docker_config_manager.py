import unittest

from golem.docker.config import DockerConfigManager
from golem.tools.ci import ci_skip


@ci_skip
class TestDockerConfigManager(unittest.TestCase):

    class MockConfig(object):
        def __init__(self, num_cores, max_memory_size, max_resource_size):
            self.num_cores = num_cores
            self.max_memory_size = max_memory_size
            self.max_resource_size = max_resource_size

        def to_dict(self):
            return dict(
                num_cores=self.num_cores,
                max_memory_size=self.max_memory_size,
                max_resource_size=self.max_resource_size,
            )

    def test_build_config(self):
        cm = DockerConfigManager()
        config = self.MockConfig(2, 1024, 2048)

        cm.build_config(config)

        self.assertGreater(len(cm._container_host_config), len(config.to_dict()))
        self.assertEqual(cm._container_host_config, cm._container_host_config)

        assert cm._container_host_config['cpuset']
        assert cm._container_host_config['mem_limit']

    def test_failing_build_config(self):

        cm = DockerConfigManager()
        cm.cpu_cores = None
        cm.build_config(None)

        self.assertFalse('cpuset' in cm._container_host_config)
        self.assertFalse('mem_limit' in cm._container_host_config)
