import copy
import logging
import os
import threading
import time
from threading import Thread, Lock


logger = logging.getLogger("golem.task.taskthread")


class TaskThread(Thread):
    def __init__(self, task_computer, subtask_id, working_directory, src_code,
                 extra_data, short_desc, res_path, tmp_path, timeout=0):
        super(TaskThread, self).__init__()

        self.task_computer = task_computer
        self.vm = None
        self.subtask_id = subtask_id
        self.src_code = src_code
        self.extra_data = extra_data
        self.short_desc = short_desc
        self.result = None
        self.done = False
        self.res_path = res_path
        self.tmp_path = tmp_path
        self.working_directory = working_directory
        self.prev_working_directory = ""
        self.lock = Lock()
        self.error = False
        self.error_msg = ""
        self.start_time = time.time()
        self.end_time = None
        self.use_timeout = timeout != 0
        self.task_timeout = timeout
        self.time_to_compute = self.task_timeout
        self.last_time_checking = time.time()

        self._parent_thread = threading.current_thread()

    def check_timeout(self):
        if not self._parent_thread.is_alive():
            self._fail("Task terminated")
        elif self.use_timeout:
            time_ = time.time()
            self.task_timeout -= time_ - self.last_time_checking
            self.last_time_checking = time_
            if self.task_timeout < 0:
                self._fail("Task timed out {:.1f}s".format(self.time_to_compute))

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

    def run(self):
        logger.info("RUNNING ")
        try:
            self.__do_work()
        except Exception as exc:
            logger.exception("__do_work failed")
            self._fail(exc)
        else:
            self.task_computer.task_computed(self)

    def end_comp(self):
        self.end_time = time.time()
        if self.vm:
            self.vm.end_comp()

    def _fail(self, error_obj):
        logger.error("Task computing error: {}".format(error_obj))
        self.error = True
        self.error_msg = str(error_obj)
        self.done = True
        self.task_computer.task_computed(self)

    def __do_work(self):
        extra_data = copy.copy(self.extra_data)

        abs_res_path = os.path.abspath(os.path.normpath(self.res_path))
        abs_tmp_path = os.path.abspath(os.path.normpath(self.tmp_path))

        self.prev_working_directory = os.getcwd()
        os.chdir(os.path.join(abs_res_path,
                              os.path.normpath(self.working_directory)))
        try:
            extra_data["resourcePath"] = abs_res_path
            extra_data["tmp_path"] = abs_tmp_path
            self.result, self.error_msg = self.vm.run_task(self.src_code, extra_data)
        finally:
            self.end_time = time.time()
            os.chdir(self.prev_working_directory)
