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
    # pylint:disable=too-many-instance-attributes
    def __init__(self, subtask_id, src_code, extra_data,
                 short_desc, res_path, tmp_path, timeout=0) -> None:
        super(TaskThread, self).__init__()

        self.vm = None
        self.subtask_id = subtask_id
        self.src_code = src_code
        self.extra_data = extra_data
        self.short_desc = short_desc
        self.result = None
        self.done = False
        self.res_path = res_path
        self.tmp_path = tmp_path
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

    def get_subtask_id(self):
        return self.subtask_id

    def get_task_short_desc(self):
        return self.short_desc

    def get_progress(self):
        with self.lock:
            return self.vm.get_progress()

    def get_error(self):
        with self.lock:
            return self.error

    def start(self) -> Deferred:
        super().start()
        return self._deferred

    def run(self):
        logger.info("RUNNING ")
        try:
            self.__do_work()
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("__do_work failed")
            self._fail(exc)
        else:
            self._deferred.callback(self)

    def end_comp(self):
        self.end_time = time.time()
        if self.vm:
            self.vm.end_comp()

    def _fail(self, exception: Exception):
        # Preserves the original cause of failure
        if self.error:
            return
        # Terminate computation (if any)
        self.end_comp()

        logger.warning("Task computing error")

        self.error = True
        self.error_msg = str(exception)
        self.done = True
        self._deferred.errback(exception)

    def __do_work(self):
        extra_data = copy.copy(self.extra_data)

        abs_res_path = os.path.abspath(os.path.normpath(self.res_path))
        abs_tmp_path = os.path.abspath(os.path.normpath(self.tmp_path))

        try:
            extra_data["resourcePath"] = abs_res_path
            extra_data["tmp_path"] = abs_tmp_path
            self.result, self.error_msg = self.vm.run_task(
                self.src_code,
                extra_data
            )
        finally:
            self.end_time = time.time()
