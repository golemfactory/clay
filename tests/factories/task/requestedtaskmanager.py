# pylint: disable=attribute-defined-outside-init,too-many-instance-attributes
import os
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

    app_manager = factory.LazyAttribute(Mock)
    env_manager = factory.LazyAttribute(Mock)
    root_path = factory.LazyAttribute(Mock)
    public_key = factory.LazyAttribute(lambda _: os.urandom(32))

    @factory.post_generation
    def _setup_async_mocks(self, *_, **__):
        methods = [
            'abort_subtask',
            'abort_task',
            'delete_task',
            'discard_subtasks',
            'duplicate_task',
            'get_next_subtask',
            'has_pending_subtasks',
            'init_task',
            'restart_subtasks',
            'restart_task',
            'stop',
            'verify',
            'work_offer_canceled',
        ]

        for method in methods:
            setattr(self, method, async_done_mock_fn())


def _create_has_pending_subtasks(_):
    return AsyncMock(return_value=True)


def _create_create_task(_):
    task = Mock(
        env_id='env',
        prerequisites={},
        inf_requirements=Mock(min_memory_mib=1000.))
    return AsyncMock(return_value=task)


def _create_next_subtask(_):
    return AsyncMock(return_value=Mock(
        params={},
        resources=['resource_1', 'resource_2']))


class MockRequestorAppClient(factory.Factory):
    class Meta:
        model = AsyncMock

    abort_task = factory.LazyAttribute(AsyncMock)
    has_pending_subtasks = factory.LazyAttribute(_create_has_pending_subtasks)
    create_task = factory.LazyAttribute(_create_create_task)
    next_subtask = factory.LazyAttribute(_create_next_subtask)
