import unittest

from golem.docker.config_manager import DockerConfigManager
from golem.docker.task_thread import DockerTaskThread


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

        assert len(cm.container_host_config) > len(config.to_dict())
        assert DockerTaskThread.container_host_config == cm.container_host_config

    def test_try(self):
        cm = DockerConfigManager()
        with cm._try():
            raise Exception("Not supposed to be raised further")
