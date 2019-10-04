import asyncio
import logging
from concurrent import futures
from typing import Dict, Callable, Optional, Coroutine, Any, Tuple

from golem_task_api.enums import VerifyResult

from golem.core.common import get_timestamp_utc
from golem.task import SubtaskId, TaskId
from golem.task.verification.queue.backend import QueueBackend, \
    DatabaseQueueBackend

logger = logging.getLogger(__name__)

VerifyFn = Callable[[TaskId, SubtaskId], Coroutine[Any, Any, VerifyResult]]


def _next_priority() -> int:
    return int(get_timestamp_utc() * 10 ** 6)


class VerificationQueue:
    """ Asynchronous verification queue for subtask results.

        Queued items are processed in order of their enqueuing time, ascending.

        - if the verification process results in VerifyResult.AWAITING_DATA,
        the item is re-queued with priority set to None,
        - after verifying an item from the queue, items with None priority
        are assigned a valid priority to re-schedule their processing.

        These prevent never ending loops caused by re-enqueuing.
    """

    DEFAULT_TIMEOUT: float = 1800.

    def __init__(
            self,
            verify_fn: VerifyFn,
            verify_timeout: float = DEFAULT_TIMEOUT,
            backend: Optional[QueueBackend] = None,
    ) -> None:
        # Provided verification function
        self._verify_fn = verify_fn
        # Verification call timeout
        self._verify_timeout = verify_timeout
        # Pending verification lock
        self._verify_lock = asyncio.Lock()
        # Queue to store requested verifications in
        self._queue = backend or DatabaseQueueBackend()
        # In-memory store for pending calls
        self._pending: Dict[Tuple[TaskId, SubtaskId], asyncio.Future] = dict()
        self._pending: Dict[Tuple[TaskId, SubtaskId], asyncio.Future] = dict()
        # Tells whether the queue processing is running
        self._processing = False
        # Tells whether queue processing was paused by the user
        self._paused = False

    async def pause(self):
        """ Pause processing the queue.
            Wait for the pending verification to finish """
        async with self._verify_lock:
            self._paused = True

    async def resume(self):
        """ Resume processing the queue """
        self._paused = False
        await self.process()

    def put(
            self,
            task_id: TaskId,
            subtask_id: SubtaskId,
    ) -> asyncio.Future:
        """ Put a new verification request into the queue.
            Start processing the queue in background """
        created = self._queue.put(
            task_id,
            subtask_id,
            priority=_next_priority())

        if created:
            self._pending[(task_id, subtask_id)] = asyncio.Future()

        asyncio.ensure_future(self.process())
        return self._pending[(task_id, subtask_id)]

    async def process(self):
        """ Process queued items one-by-one, ordered by their priority.
            Skip items with priority equal to None """
        if self._processing:
            return
        try:
            self._processing = True
            await self._process()
        finally:
            self._processing = False

    async def _process(self):
        if self._paused:
            return

        async with self._verify_lock:
            queued = self._queue.get()
            if not queued:
                return

            task_id, subtask_id = queued
            await self._verify(task_id, subtask_id)
            self._queue.update_not_prioritized(_next_priority)

        await self._process()

    async def _verify(
            self,
            task_id: TaskId,
            subtask_id: SubtaskId,
    ) -> None:
        try:
            result = await asyncio.wait_for(
                fut=self._verify_fn(task_id, subtask_id),
                timeout=self._verify_timeout)
        except futures.TimeoutError:
            result = VerifyResult.FAILURE
            logger.error("Verification timeout: subtask_id=%s", subtask_id)

        if result is VerifyResult.AWAITING_DATA:
            self._queue.put(
                task_id,
                subtask_id,
                priority=None)
        else:
            # The queue is persistent, there may be no Future object in memory
            future = self._pending.pop((task_id, subtask_id), None)
            if future:
                future.set_result(result)
