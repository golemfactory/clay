import logging
import threading
import queue
from types import FunctionType
from typing import Optional, Type, Dict
from collections import namedtuple
from twisted.internet.defer import Deferred, gatherResults
from apps.blender.blender_reference_generator import BlenderReferenceGenerator
from golem_verificator.verifier import Verifier
from golem.core.common import deadline_to_timeout
from golem.task.localcomputer import ComputerAdapter

logger = logging.getLogger("apps.blender.verification")


class VerificationQueue:

    Entry = namedtuple('Entry', ['verifier_class', 'subtask_id',
                                 'deadline', 'kwargs', 'cb'])

    def __init__(self, concurrency: int = 1) -> None:

        self._concurrency = concurrency
        self._queue: queue.Queue = queue.Queue()

        self._lock = threading.Lock()
        self._jobs: Dict[str, Deferred] = dict()
        self._paused = False

    def submit(self,
               verifier_class: Type[Verifier],
               subtask_id: str,
               deadline: int,
               cb: FunctionType,
               **kwargs) -> None:

        entry = self.Entry(verifier_class, subtask_id, deadline, kwargs, cb)
        self._queue.put(entry)
        self._process_queue()

    def pause(self) -> Deferred:
        self._paused = True
        deferred_list = list(self._jobs.values())
        return gatherResults(deferred_list)

    def resume(self) -> None:
        self._paused = False
        self._process_queue()

    @property
    def can_run(self) -> bool:
        with self._lock:
            return not self._paused and len(self._jobs) < self._concurrency

    def _process_queue(self) -> None:
        if self.can_run:
            entry = self._next()
            if entry:
                self._run(entry)

    def _next(self) -> Optional['Entry']:
        try:
            return self._queue.get(block=False)
        except queue.Empty:
            return None

    def _run(self, entry: Entry) -> None:
        deferred_job = Deferred()
        subtask_id = entry.subtask_id

        with self._lock:
            self._jobs[subtask_id] = deferred_job

        logger.info("Running verification of subtask %r", subtask_id)

        def callback(*args, **kwargs):
            with self._lock:
                deferred_job.callback(True)
                self._jobs.pop(subtask_id, None)

            logger.info("Finished verification of subtask %r", subtask_id)
            try:
                entry.cb(*args, **kwargs)
            finally:
                self._process_queue()

        try:
            entry.kwargs["reference_generator"] = BlenderReferenceGenerator()
            verifier = entry.verifier_class(callback, entry.kwargs)
            verifier.computer = ComputerAdapter()
            if deadline_to_timeout(entry.deadline) > 0:
                if not verifier.simple_verification(entry.kwargs):
                    verifier.verification_completed()
                else:
                    verifier.start_verification(entry.kwargs)
            else:
                verifier.task_timeout(subtask_id)
                raise Exception("Task deadline passed")

        except Exception as exc:  # pylint: disable=broad-except
            with self._lock:
                deferred_job.errback(exc)
                self._jobs.pop(subtask_id, None)

            logger.error("Failed to start verification of subtask %r: %r",
                         subtask_id, exc)
            self._process_queue()

    def _reset(self) -> None:
        self._queue = queue.Queue()
        self._jobs = dict()
