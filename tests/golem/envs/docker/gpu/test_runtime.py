from unittest import TestCase, mock

from golem.envs.docker.gpu import DockerGPURuntime


class TestRuntime(TestCase):

    def setUp(self) -> None:
        self.runtime = DockerGPURuntime(
            container_config=dict(
                image='golemfactory/test',
                command='/bin/false'
            ),
            port_mapper=mock.Mock()
        )

    def test_usage_counters(self):
        with self.assertRaises(NotImplementedError):
            self.runtime.usage_counters()
