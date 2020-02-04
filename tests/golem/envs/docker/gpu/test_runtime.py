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
