import logging
import queue
import os
import threading

from collections import namedtuple
from datetime import datetime
from types import FunctionType
from typing import Optional, Type, Dict

from twisted.internet.defer import Deferred, gatherResults

from golem.core.common import deadline_to_timeout
from golem.task.localcomputer import ComputerAdapter

from golem.verification.verifier import (StateVerifier,
                                         SubtaskVerificationState, Verifier)

logger = logging.getLogger("apps.core")


class CoreVerifier(StateVerifier):

    def start_verification(self, subtask_info: dict, reference_data: list,
                           resources: list, results: list):
        super(CoreVerifier, self).start_verification(subtask_info,
                                                     reference_data,
                                                     resources,
                                                     results)
        self._check_files(subtask_info, results, reference_data, resources)

    def _check_files(self, subtask_info, results, reference_data, resources):
        for result in results:
            if os.path.isfile(result):
                if self._verify_result(subtask_info, result, reference_data,
                                       resources):
                    self.state = SubtaskVerificationState.VERIFIED
                    self.verification_completed()
                    return
        self.state = SubtaskVerificationState.WRONG_ANSWER
        self.message = "No proper task result found"
        self.verification_completed()

    def verification_completed(self):
        self.time_ended = datetime.utcnow()
        self.extra_data['results'] = self.results
        self.callback(subtask_id=self.subtask_info['subtask_id'],
                      verdict=self.state,
                      result=self._get_answer())

    # pylint: disable=unused-argument
    def _verify_result(self, subtask_info: dict, result: str,
                       reference_data: list, resources: list):
        """ Override this to change verification method
        """
        return True


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
            verifier = entry.verifier_class(callback)
            verifier.computer = ComputerAdapter()
            if deadline_to_timeout(entry.deadline) > 0:
                verifier.start_verification(**entry.kwargs)
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
