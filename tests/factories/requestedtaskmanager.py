# pylint: disable=attribute-defined-outside-init,too-many-instance-attributes
from asyncio import Future
from unittest.mock import Mock

import factory

from golem.task import requestedtaskmanager
from tests.utils.asyncio import AsyncMock


def async_done_mock_fn() -> Future:
    future: Future = Future()
    future.done()
    return AsyncMock(return_value=future)


class MockRequestedTaskManager(factory.Factory):
    class Meta:
        model = requestedtaskmanager.RequestedTaskManager

    env_manager = Mock()
    app_manager = Mock()
    public_key = b'0' * 32
    root_path = Mock()

    @factory.post_generation
    def _setup_async_mocks(self, *_, **__):
        self.abort_subtask = async_done_mock_fn()
        self.abort_task = async_done_mock_fn()
        self.delete_task = async_done_mock_fn()
        self.discard_subtasks = async_done_mock_fn()
        self.duplicate_task = async_done_mock_fn()
        self.get_next_subtask = async_done_mock_fn()
        self.has_pending_subtasks = async_done_mock_fn()
        self.init_task = async_done_mock_fn()
        self.restart_subtasks = async_done_mock_fn()
        self.restart_task = async_done_mock_fn()
        self.stop = async_done_mock_fn()
        self.verify = async_done_mock_fn()
        self.work_offer_canceled = async_done_mock_fn()
