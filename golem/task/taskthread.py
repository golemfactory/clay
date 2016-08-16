import copy
import logging
import os
import threading
import time
from threading import Thread, Lock


logger = logging.getLogger(__name__)


class ParentThreadMonitor(Thread):
    def __init__(self, parent_thread, terminate_func):
        super(ParentThreadMonitor, self).__init__(target=self._monitor)
        self._parent_thread = parent_thread
        self._terminate_func = terminate_func
        self._interval = 1
        self.daemon = True
        self.working = False

    def stop(self):
        self.working = False
        if self.is_alive():
            self.join()

    def _monitor(self):
        self.working = True
        while self.working:
            self._parent_thread.join(self._interval)
            # despite being an active parent thread, is_alive returns False
            # if the application is shutting down
            if not self._parent_thread.is_alive():
                self.working = False
                self._terminate_func()
                return


class TaskThread(Thread):
    def __init__(self, task_computer, subtask_id, working_directory, src_code,
                 extra_data, short_desc, res_path, tmp_path, timeout=0):
        super(TaskThread, self).__init__()

        self.task_computer = task_computer
        self.parent_monitor = ParentThreadMonitor(threading.current_thread(),
                                                  terminate_func=self.end_comp)
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

    def check_timeout(self):
        if not self.use_timeout:
            return
        time_ = time.time()
        self.task_timeout -= time_ - self.last_time_checking
        self.last_time_checking = time_
        if self.task_timeout < 0:
            self.error = True
            self.error_msg = "Task timed out {:.1f}s".format(self.time_to_compute)
            self.end_comp()

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

    def start(self):
        self.parent_monitor.start()
        super(TaskThread, self).start()

    def run(self):
        logger.info("RUNNING ")
        try:
            self.__do_work()
        except Exception as exc:
            logger.error("Task computing error: {}".format(exc))
            self.error = True
            self.error_msg = str(exc)
            self.done = True
        finally:
            self.task_computer.task_computed(self)
            self.parent_monitor.stop()

    def end_comp(self):
        self.end_time = time.time()
        if self.vm:
            self.vm.end_comp()

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
