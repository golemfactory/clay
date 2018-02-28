import logging
import queue
import threading
import time
from collections import namedtuple
from datetime import datetime
import os
from types import FunctionType
from typing import Optional, Type

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

    Entry = namedtuple('Entry', ['created', 'kwargs', 'cb'])

    def __init__(self,
                 verifier_class: Type[Verifier],
                 concurrency: int = 2) -> None:

        self._verifier_class = verifier_class
        self._concurrency = concurrency
        self._queue: queue.Queue = queue.Queue()

        self._lock = threading.Lock()
        self._running = 0

    def submit(self, cb: FunctionType, **kwargs) -> None:
        entry = self.Entry(time.time(), kwargs, cb)
        self._queue.put(entry)
        self._process_queue()

    @property
    def can_run(self) -> bool:
        with self._lock:
            return self._running < self._concurrency

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
        with self._lock:
            self._running += 1

        subtask_info = entry.kwargs['subtask_info']
        logger.info("Running verification for subtask %r", subtask_info)

        def callback(*args, **kwargs):
            with self._lock:
                self._running -= 1

            logger.info("Finished verification for subtask %r", subtask_info)

            entry.cb(*args, **kwargs)
            self._process_queue()

        try:
            verifier = self._verifier_class(callback)
            verifier.computer = ComputerAdapter()
            verifier.start_verification(**entry.kwargs)
        except Exception as exc:  # pylint: disable=broad-except
            with self._lock:
                self._running -= 1

            logger.error("Failed to start verification for subtask %r: %r",
                         subtask_info, exc)
            self._process_queue()
