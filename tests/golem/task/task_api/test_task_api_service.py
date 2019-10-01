from pathlib import Path

from unittest import TestCase
from unittest.mock import Mock

from twisted.internet import defer

from golem.testutils import async_test
from golem.envs import (
    Environment,
    Prerequisites,
    Runtime
)
from golem.task.task_api import (
    EnvironmentTaskApiService,
    TaskApiPayloadBuilder,
)


class TestTaskApiService(TestCase):

    def setUp(self):
        self.runtime = Mock(spec_set=Runtime)
        self.runtime.prepare.return_value = defer.succeed(None)
        self.runtime.start.return_value = defer.succeed(None)
        self.runtime.stop.return_value = defer.succeed(None)
        self.runtime.wait_until_stopped.return_value = defer.succeed(None)
        self.runtime.clean_up.return_value = defer.succeed(None)
        self.env = Mock(spec_set=Environment)
        self.env.runtime.return_value = self.runtime
        self.prereq = Mock(spec_set=Prerequisites)
        self.shared_dir = Mock(spec_set=Path)
        self.payload_builder = Mock(spec_set=TaskApiPayloadBuilder)
        self.service = EnvironmentTaskApiService(
            self.env,
            self.prereq,
            self.shared_dir,
            self.payload_builder,
        )

    @async_test
    async def test_start(self):
        command = 'test_command'
        port = 1234
        socket_addr = await self.service.start(command, port)
        self.payload_builder.create_payload.assert_called_once_with(
            self.prereq,
            self.shared_dir,
            command,
            port,
        )
        self.env.runtime.assert_called_once_with(
            self.payload_builder.create_payload.return_value,
        )
        self.runtime.prepare.assert_called_once_with()
        self.runtime.start.assert_called_once_with()
        self.runtime.get_port_mapping.assert_called_once_with(port)
        self.assertEqual(self.runtime.get_port_mapping(), socket_addr)

    @async_test
    async def test_stop(self):
        await self.service.start('cmd', 1234)
        await self.service.stop()
        self.runtime.stop.assert_called_once_with()

    @async_test
    async def test_wait_until_shutdown_complete(self):
        await self.service.start('cmd', 1234)
        await self.service.wait_until_shutdown_complete()
        self.runtime.wait_until_stopped.assert_called_once_with()
        self.runtime.clean_up.assert_called_once_with()
