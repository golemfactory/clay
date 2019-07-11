from pathlib import Path

from unittest import TestCase
from unittest.mock import Mock

from golem.testutils import async_test
from golem.envs import Environment, Prerequisites
from golem.task.appcallbacks.appcallbacks import (
    EnvironmentCallbacks,
    TaskApiPayloadBuilder,
)


class TestAppCallbacks(TestCase):
    def setUp(self):
        self.env = Mock(spec_set=Environment)
        self.prereq = Mock(spec_set=Prerequisites)
        self.shared_dir = Mock(spec_set=Path)
        self.payload_maker = Mock(spec_set=TaskApiPayloadBuilder)
        self.app_callbacks = EnvironmentCallbacks(
            self.env,
            self.prereq,
            self.shared_dir,
            self.payload_maker,
        )

    def test_spawn_server(self):
        command = 'test_command'
        port = 1234
        socket_addr = self.app_callbacks.spawn_server(command, port)
        self.payload_maker.create_payload.assert_called_once_with(
            self.prereq,
            self.shared_dir,
            command,
            port,
        )
        self.env.runtime.assert_called_once_with(
            self.payload_maker.create_payload.return_value,
        )
        runtime = self.env.runtime.return_value
        runtime.prepare.assert_called_once_with()
        runtime.start.assert_called_once_with()
        runtime.get_port_mapping.assert_called_once_with(port)
        self.assertEqual(runtime.get_port_mapping.return_value, socket_addr)

    @async_test
    async def test_wait_after_shutdown(self):
        runtime = self.env.runtime.return_value
        self.app_callbacks.spawn_server('cmd', 1234)
        await self.app_callbacks.wait_after_shutdown()
        runtime.wait_until_stopped.assert_called_once_with()
