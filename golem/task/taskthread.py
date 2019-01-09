import abc
import copy
import logging
import os
import threading
import time
from typing import Any, Dict, Tuple, Union

from twisted.internet.defer import Deferred


logger = logging.getLogger("golem.task.taskthread")


class JobException(RuntimeError):
    pass


class TimeoutException(JobException):
    pass


class TaskThread(threading.Thread):
    result: Union[None, Dict[str, Any], Tuple[Dict[str, Any], int]] = None

    # pylint:disable=too-many-arguments
    def __init__(self,
                 src_code: str,
                 extra_data: Dict,
                 timeout: float = 0) -> None:
        super(TaskThread, self).__init__()

        self.src_code = src_code
        self.extra_data = extra_data
        self.result = None
        self.done = False
        self.lock = threading.Lock()
        self.error = False
        self.error_msg = ""
        self.start_time = time.time()
        self.end_time = None
        self.use_timeout = timeout != 0
        self.task_timeout = timeout
        self.time_to_compute = self.task_timeout
        self.last_time_checking = time.time()

        self._parent_thread = threading.current_thread()
        self._deferred = Deferred()

    def check_timeout(self):
        if not self._parent_thread.is_alive():
            try:
                raise JobException("Task terminated")
            except JobException as e:
                self._fail(e)
        elif self.use_timeout:
            time_ = time.time()
            self.task_timeout -= time_ - self.last_time_checking
            self.last_time_checking = time_
            if self.task_timeout < 0:
                try:
                    raise TimeoutException("Task timed out {:.1f}s"
                                           .format(self.time_to_compute))
                except TimeoutException as e:
                    self._fail(e)

    @abc.abstractmethod
    def get_progress(self):
        pass

    def get_error(self):
        with self.lock:
            return self.error

    def start(self) -> Deferred:
        super().start()
        return self._deferred

    @abc.abstractmethod
    def run(self):
        pass

    def end_comp(self):
        self.end_time = time.time()

    def _fail(self, exception: Exception):
        # Preserves the original cause of failure
        if self.error:
            return
        # Terminate computation (if any)
        self.end_comp()

        logger.warning("Task computing error %s", exception)

        self.error = True
        self.error_msg = str(exception)
        self.done = True
        self._deferred.errback(exception)
