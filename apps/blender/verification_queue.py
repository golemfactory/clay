import logging
import queue
from types import FunctionType
from typing import Optional, Type, Dict, Tuple
from apps.blender.verification_task import VerificationTask

from twisted.internet.defer import Deferred, gatherResults

from golem_verificator.verifier import Verifier

logger = logging.getLogger("apps.blender.verification")


class VerificationQueue:

    def __init__(self, concurrency: int = 1) -> None:
        self._concurrency = concurrency
        self._queue: queue.Queue = queue.Queue()
        self._jobs: Dict[str, Deferred] = dict()
        self.callbacks: Dict[VerificationTask, Tuple[FunctionType,
                                                     Type[Verifier]]] = dict()
        self._paused = False

    def submit(self,
               verifier_class: Type[Verifier],
               subtask_id: str,
               deadline: int,
               cb: FunctionType,
               **kwargs) -> None:

        logger.debug(
            "Verification Queue submit: "
            "(verifier_class: %s, subtask: %s, deadline: %s, kwargs: %s)",
            verifier_class, subtask_id, deadline, kwargs
        )

        entry = VerificationTask(subtask_id, deadline, kwargs)
        self.callbacks[entry] = cb
        self._queue.put((entry, verifier_class))
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
        return not self._paused and len(self._jobs) < self._concurrency

    def _process_queue(self) -> None:
        if self.can_run:
            try:
                entry, verifier_cls = self._next()
                if entry:
                    self._run(entry, verifier_cls)
            except TypeError:
                # If queue is empty we can't assign None to Tuple
                pass

    def _next(self) -> Optional['Entry']:
        try:
            return self._queue.get(block=False)
        except queue.Empty:
            return None

    def _run(self, entry: VerificationTask,
             verifier_cls: Type[Verifier]) -> None:
        subtask_id = entry.subtask_id

        logger.info("Running verification of subtask %r", subtask_id)

        def callback(*args, **kwargs):
            logger.info("Finished verification of subtask %r", subtask_id)
            try:
                self.callbacks[entry](*args, ** kwargs)
            finally:
                self._jobs.pop(subtask_id, None)
                self._process_queue()

        result = entry.start(callback, verifier_cls)
        if result:
            self._jobs[subtask_id] = result

    def _reset(self) -> None:
        self._queue = queue.Queue()
        self._jobs = dict()
