# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name
# ^^ Pytest fixtures in the same file require the same name

import asyncio
from unittest import mock

import pytest
from golem_task_api.enums import VerifyResult

from golem.task import SubtaskId, TaskId
from golem.task.verification.queue import VerificationQueue
from golem.testutils import pytest_database_fixture  # noqa pylint: disable=unused-import
from tests.utils.asyncio import AsyncMock

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

    @pytest.fixture(autouse=True)
    def setup_method(self, event_loop):  # fixture: use the same event loop
        self.queue = VerificationQueue(verify_fn)

    @pytest.mark.asyncio
    async def test_put_duplicate(self):
        self.queue.process = AsyncMock()
        assert not self.queue._pending.get((TASK_ID, SUBTASK_ID))

        future = self.queue.put(TASK_ID, SUBTASK_ID)
        assert self.queue._pending.get((TASK_ID, SUBTASK_ID)) is future

        future2 = self.queue.put(TASK_ID, SUBTASK_ID)
        assert self.queue._pending.get((TASK_ID, SUBTASK_ID)) is future
        assert future2 is future


@pytest.mark.usefixtures('pytest_database_fixture')
class TestProcessPublicMethod:

    @pytest.fixture(autouse=True)
    def setup_method(self, event_loop):  # fixture: use the same event loop
        self.queue = VerificationQueue(verify_fn)

    @pytest.mark.asyncio
    async def test(self):
        self.queue._process = AsyncMock()
        assert not self.queue._processing

        await self.queue.process()
        assert self.queue._process.called
        assert not self.queue._processing

    @pytest.mark.asyncio
    async def test_while_processing(self):
        self.queue._process = AsyncMock()
        self.queue._processing = True

        await self.queue.process()
        assert not self.queue._process.called


@pytest.mark.usefixtures('pytest_database_fixture')
class TestProcessProtectedMethod:

    @pytest.fixture(autouse=True)
    def setup_method(self, event_loop):  # fixture: use the same event loop
        self.queue = VerificationQueue(verify_fn)

    @pytest.mark.asyncio
    async def test_while_paused(self):
        self.queue._paused = True
        self.queue._verify = AsyncMock()
        self.queue._queue.update_not_prioritized = mock.Mock()

        await self.queue._process()
        assert not self.queue._verify.called
        assert not self.queue._queue.update_not_prioritized.called

    @pytest.mark.asyncio
    async def test_empty_queue(self):
        self.queue._verify = AsyncMock()
        self.queue._queue.update_not_prioritized = mock.Mock()

        await self.queue._process()
        assert not self.queue._verify.called
        assert not self.queue._queue.update_not_prioritized.called

    @pytest.mark.asyncio
    async def test_loop(self):
        self.queue.process = AsyncMock()
        self.queue._verify = AsyncMock(wraps=self.queue._verify)
        self.queue._queue.update_not_prioritized = mock.Mock()

        # Auto-processing in put was disabled by mocking queue.process
        _ = self.queue.put(f"{TASK_ID}1", f"{SUBTASK_ID}1")
        _ = self.queue.put(f"{TASK_ID}2", f"{SUBTASK_ID}2")

        await self.queue._process()
        assert self.queue._verify.call_count == 2
        assert self.queue._queue.update_not_prioritized.call_count == 2


@pytest.mark.usefixtures('pytest_database_fixture')
class TestVerify:

    @pytest.fixture(autouse=True)
    def setup_method(self, event_loop):  # fixture: use the same event loop
        self.queue = VerificationQueue(verify_fn)

    @pytest.mark.asyncio
    async def test(self):
        self.queue.process = AsyncMock()

        # Auto-processing in put was disabled by mocking queue.process
        future = self.queue.put(TASK_ID, SUBTASK_ID)

        assert (TASK_ID, SUBTASK_ID) in self.queue._pending
        await self.queue._verify(TASK_ID, SUBTASK_ID)
        assert (TASK_ID, SUBTASK_ID) not in self.queue._pending

        await future
        assert future.result() is VerifyResult.SUCCESS

    @pytest.mark.asyncio
    async def test_no_future(self):
        self.queue.process = AsyncMock()

        # Auto-processing in put was disabled by mocking queue.process
        assert (TASK_ID, SUBTASK_ID) not in self.queue._pending
        await self.queue._verify(TASK_ID, SUBTASK_ID)
        assert (TASK_ID, SUBTASK_ID) not in self.queue._pending

    @pytest.mark.asyncio
    async def test_timeout(self):
        self.queue.process = AsyncMock()
        self.queue._verify_timeout = 0.01

        # Auto-processing in put was disabled by mocking queue.process
        future = self.queue.put(TASK_ID, SUBTASK_ID)

        await self.queue._verify(TASK_ID, SUBTASK_ID)
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

        self.queue = VerificationQueue(verify_awaiting)
        self.queue.process = AsyncMock()

        # Auto-processing in put was disabled by mocking queue.process
        future = self.queue.put(TASK_ID, SUBTASK_ID)

        self.queue._queue.put = mock.Mock()
        await self.queue._verify(TASK_ID, SUBTASK_ID)

        assert not future.done()
        self.queue._queue.put.assert_called_with(
            TASK_ID,
            SUBTASK_ID,
            priority=None)


@pytest.mark.usefixtures('pytest_database_fixture')
class TestPause:

    @pytest.fixture(autouse=True)
    def setup_method(self, event_loop):  # fixture: use the same event loop
        self.queue = VerificationQueue(verify_fn)

    @pytest.mark.asyncio
    async def test_pause_resume(self):
        await self.queue.pause()
        assert self.queue._paused

        await self.queue.resume()
        assert not self.queue._paused

    @pytest.mark.asyncio
    async def test_pause_resume_while_processing(self):
        future = self.queue.put(TASK_ID, SUBTASK_ID)
        await asyncio.sleep(0.1)

        await self.queue.pause()
        assert self.queue._paused
        assert future.result()

        await self.queue.resume()
        assert not self.queue._paused
