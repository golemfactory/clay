from pathlib import Path

from unittest import TestCase
from unittest.mock import Mock

from golem.testutils import async_test
from golem.envs import Environment, Prerequisites
from golem.task.task_api import (
    EnvironmentTaskApiService,
    TaskApiPayloadBuilder,
)


class TestTaskApiService(TestCase):
    def setUp(self):
        self.env = Mock(spec_set=Environment)
        self.prereq = Mock(spec_set=Prerequisites)
        self.shared_dir = Mock(spec_set=Path)
        self.payload_builder = Mock(spec_set=TaskApiPayloadBuilder)
        self.service = EnvironmentTaskApiService(
            self.env,
            self.prereq,
            self.shared_dir,
            self.payload_builder,
        )

    def test_start(self):
        command = 'test_command'
        port = 1234
        socket_addr = self.service.start(command, port)
        self.payload_builder.create_payload.assert_called_once_with(
            self.prereq,
            self.shared_dir,
            command,
            port,
        )
        self.env.runtime.assert_called_once_with(
            self.payload_builder.create_payload.return_value,
        )
        runtime = self.env.runtime.return_value
        runtime.prepare.assert_called_once_with()
        runtime.start.assert_called_once_with()
        runtime.get_port_mapping.assert_called_once_with(port)
        self.assertEqual(runtime.get_port_mapping.return_value, socket_addr)

    @async_test
    async def test_wait_until_shutdown_complete(self):
        runtime = self.env.runtime.return_value
        self.service.start('cmd', 1234)
        await self.service.wait_until_shutdown_complete()
        runtime.wait_until_stopped.assert_called_once_with()
