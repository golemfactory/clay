import logging
import queue
from functools import partial
from types import FunctionType
from typing import Optional, Type, Dict, Tuple

from golem.verifier.core_verifier import CoreVerifier
from twisted.internet.defer import Deferred, gatherResults

from apps.core.verification_task import VerificationTask

logger = logging.getLogger(__name__)


class VerificationQueue:

    #  We assume that after 30 minutes verification tasks is stalled (possibly
    #  to bugs in third party docker api). After this period we finish
    #  verification tasks with fail. In future this constant will be
    #  configurable from config, and will be relative to nodes benchmark
    #  results.
    VERIFICATION_TIMEOUT = 1800

    def __init__(self, concurrency: int = 1) -> None:
        self._concurrency = concurrency
        self._queue: queue.Queue = queue.Queue()
        self._jobs: Dict[str, Deferred] = dict()
        self.callbacks: Dict[VerificationTask, FunctionType] = dict()
        self._paused = False

    def submit(self,
               verifier_class: Type[CoreVerifier],
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
            entry, verifier_cls = self._next()
            if entry and verifier_cls:
                self._run(entry, verifier_cls)

    def _next(self) -> Tuple[Optional[VerificationTask],
                             Optional[Type[CoreVerifier]]]:
        try:
            return self._queue.get(block=False)
        except queue.Empty:
            return None, None

    def _run(self, entry: VerificationTask,
             verifier_cls: Type[CoreVerifier]) -> None:
        subtask_id = entry.subtask_id

        logger.info("Running verification of subtask %r", subtask_id)

        def callback(*args):
            logger.info("Finished verification of subtask %r", subtask_id)
            try:
                self.callbacks[entry](subtask_id=args[0][0], verdict=args[0][1],
                                      result=args[0][2])
            finally:
                self._jobs.pop(subtask_id, None)
                self._process_queue()

        def errback(_):
            logger.warning("Finishing verification with fail")
            callback(entry.get_results())
            return True

        from twisted.internet import reactor
        result = entry.start(verifier_cls)
        if result:
            result.addCallback(partial(reactor.callFromThread, callback))
            result.addErrback(partial(reactor.callFromThread, errback))

            fn_timeout = partial(self._verification_timed_out, task=entry,
                                 event=result, subtask_id=subtask_id)

            result.addTimeout(VerificationQueue.VERIFICATION_TIMEOUT, reactor,
                              onTimeoutCancel=fn_timeout)
            self._jobs[subtask_id] = result

    @staticmethod
    def _verification_timed_out(_result, _timeout, task, event,
                                subtask_id):
        logger.warning("Timeout detected for subtask %s", subtask_id)
        task.stop(event)

    def _reset(self) -> None:
        self._queue = queue.Queue()
        self._jobs = dict()
        self.callbacks = dict()
