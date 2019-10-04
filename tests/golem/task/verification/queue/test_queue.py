# pylint: disable=redefined-outer-name
# ^^ Pytest fixtures in the same file require the same name

import asyncio
from unittest import mock

import pytest
from golem_task_api.enums import VerifyResult

from golem.task import SubtaskId, TaskId
from golem.task.verification.queue import VerificationQueue
from golem.testutils import pytest_database_fixture  # noqa pylint: disable=unused-import


class AsyncMock(mock.MagicMock):
    """
    Extended MagicMock to keep async calls async
    """
    async def __call__(self, *args, **kwargs):
        return super().__call__(*args, **kwargs)


TASK_ID = 'task_id'
SUBTASK_ID = 'subtask_id'


async def verify_fn(
        _task_id: TaskId,
        _subtask_id: SubtaskId
) -> VerifyResult:
    await asyncio.sleep(0.5)
    return VerifyResult.SUCCESS


@pytest.mark.usefixtures('pytest_database_fixture')
class TestPut:

    @pytest.mark.asyncio
    async def test_put_duplicate(self):
        queue = VerificationQueue(verify_fn)
        queue.process = AsyncMock()
        assert not queue._pending.get((TASK_ID, SUBTASK_ID))

        future = queue.put(TASK_ID, SUBTASK_ID)
        assert queue._pending.get((TASK_ID, SUBTASK_ID)) is future

        future2 = queue.put(TASK_ID, SUBTASK_ID)
        assert queue._pending.get((TASK_ID, SUBTASK_ID)) is future
        assert future2 is future


@pytest.mark.usefixtures('pytest_database_fixture')
class TestProcessPublicMethod:

    @pytest.mark.asyncio
    async def test(self):
        queue = VerificationQueue(verify_fn)
        queue._process = AsyncMock()

        assert not queue._processing
        await queue.process()
        assert queue._process.called
        assert not queue._processing

    @pytest.mark.asyncio
    async def test_while_processing(self):
        queue = VerificationQueue(verify_fn)
        queue._process = AsyncMock()
        queue._processing = True

        await queue.process()
        assert not queue._process.called


@pytest.mark.usefixtures('pytest_database_fixture')
class TestProcessProtectedMethod:

    @pytest.mark.asyncio
    async def test_while_paused(self):
        queue = VerificationQueue(verify_fn)
        queue._paused = True
        queue._verify = AsyncMock()
        queue._queue.update_not_prioritized = mock.Mock()

        await queue._process()
        assert not queue._verify.called
        assert not queue._queue.update_not_prioritized.called

    @pytest.mark.asyncio
    async def test_empty_queue(self):
        queue = VerificationQueue(verify_fn)
        queue._verify = AsyncMock()
        queue._queue.update_not_prioritized = mock.Mock()

        await queue._process()
        assert not queue._verify.called
        assert not queue._queue.update_not_prioritized.called

    @pytest.mark.asyncio
    async def test_loop(self):
        queue = VerificationQueue(verify_fn)
        queue.process = AsyncMock()
        queue._verify = AsyncMock(wraps=queue._verify)
        queue._queue.update_not_prioritized = mock.Mock()

        # Auto-processing in put was disabled by mocking queue.process
        _ = queue.put(f"{TASK_ID}1", f"{SUBTASK_ID}1")
        _ = queue.put(f"{TASK_ID}2", f"{SUBTASK_ID}2")

        await queue._process()
        assert queue._verify.call_count == 2
        assert queue._queue.update_not_prioritized.call_count == 2


@pytest.mark.usefixtures('pytest_database_fixture')
class TestVerify:

    @pytest.mark.asyncio
    async def test(self):
        queue = VerificationQueue(verify_fn)
        queue.process = AsyncMock()

        # Auto-processing in put was disabled by mocking queue.process
        future = queue.put(TASK_ID, SUBTASK_ID)

        assert (TASK_ID, SUBTASK_ID) in queue._pending
        await queue._verify(TASK_ID, SUBTASK_ID)
        assert (TASK_ID, SUBTASK_ID) not in queue._pending

        await future
        assert future.result() is VerifyResult.SUCCESS

    @pytest.mark.asyncio
    async def test_no_future(self):
        queue = VerificationQueue(verify_fn)
        queue.process = AsyncMock()

        # Auto-processing in put was disabled by mocking queue.process
        assert (TASK_ID, SUBTASK_ID) not in queue._pending
        await queue._verify(TASK_ID, SUBTASK_ID)
        assert (TASK_ID, SUBTASK_ID) not in queue._pending

    @pytest.mark.asyncio
    async def test_timeout(self):
        queue = VerificationQueue(verify_fn)
        queue.process = AsyncMock()
        queue._verify_timeout = 0.01

        # Auto-processing in put was disabled by mocking queue.process
        future = queue.put(TASK_ID, SUBTASK_ID)

        await queue._verify(TASK_ID, SUBTASK_ID)
        await future
        assert future.result() is VerifyResult.FAILURE

    @pytest.mark.asyncio
    async def test_re_queue(self):

        async def verify_awaiting(
                _task_id: TaskId,
                _subtask_id: SubtaskId
        ) -> VerifyResult:
            await asyncio.sleep(0.1)
            return VerifyResult.AWAITING_DATA

        queue = VerificationQueue(verify_awaiting)
        queue.process = AsyncMock()

        # Auto-processing in put was disabled by mocking queue.process
        future = queue.put(TASK_ID, SUBTASK_ID)

        queue._queue.put = mock.Mock()
        await queue._verify(TASK_ID, SUBTASK_ID)

        assert not future.done()
        queue._queue.put.assert_called_with(TASK_ID, SUBTASK_ID, priority=None)


@pytest.mark.usefixtures('pytest_database_fixture')
class TestPause:

    @pytest.mark.asyncio
    async def test_pause_resume(self):
        queue = VerificationQueue(verify_fn)
        await queue.pause()
        assert queue._paused

        await queue.resume()
        assert not queue._paused

    @pytest.mark.asyncio
    async def test_pause_resume_while_processing(self):
        queue = VerificationQueue(verify_fn)
        future = queue.put(TASK_ID, SUBTASK_ID)
        await asyncio.sleep(0.1)

        await queue.pause()
        assert queue._paused
        assert future.result()

        await queue.resume()
        assert not queue._paused
