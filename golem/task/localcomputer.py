import logging
import os
import shutil
from threading import Lock
import time

from golem.docker.task_thread import DockerTaskThread
from golem.resource.dirmanager import get_test_task_path, get_test_task_tmp_path
from golem.resource.resource import TaskResourceHeader, decompress_dir
from golem.task.taskbase import Task, resource_types

logger = logging.getLogger("golem.task")


class LocalComputer(object):
    DEFAULT_WARNING = "Computation failed"
    DEFAULT_SUCCESS = "Task computation success!"

    def __init__(self, task, root_path, success_callback, error_callback, get_compute_task_def, check_mem=False,
                 comp_failed_warning=DEFAULT_WARNING, comp_success_message=DEFAULT_SUCCESS, use_task_resources=True,
                 additional_resources=None):
        if not isinstance(task, Task):
            raise TypeError("Incorrect task type: {}. Should be: Task".format(type(task)))
        self.task = task
        self.res_path = None
        self.tmp_dir = None
        self.success = False
        self.lock = Lock()
        self.tt = None
        self.root_path = root_path
        self.get_compute_task_def = get_compute_task_def
        self.error_callback = error_callback
        self.success_callback = success_callback
        self.check_mem = check_mem
        self.comp_failed_warning = comp_failed_warning
        self.comp_success_message = comp_success_message
        self.use_task_resources = use_task_resources
        if additional_resources is None:
            additional_resources = []
        self.additional_resources = additional_resources

        self.start_time = None
        self.end_time = None

    def run(self):
        try:
            self.start_time = time.time()
            self.__prepare_tmp_dir()
            self.__prepare_resources()

            ctd = self.get_compute_task_def()

            self.tt = self._get_task_thread(ctd)
            self.tt.start()

        except Exception as exc:
            logger.warning("{}: {}".format(self.comp_failed_warning, exc))
            self.error_callback(str(exc))

    def end_comp(self):
        if self.tt:
            self.tt.end_comp()
            return True
        else:
            return False

    def get_progress(self):
        if self.tt:
            with self.lock:
                if self.tt.get_error():
                    logger.warning(self.comp_failed_warning)
                    return 0.0
                return self.tt.get_progress()
        return None

    def task_computed(self, task_thread):
        self.end_time = time.time()
        if self.is_success(task_thread):
            self.computation_success(task_thread)
        else:
            self.computation_failure(task_thread)

    def is_success(self, task_thread):
        return not task_thread.error and task_thread.result and task_thread.result.get("data")

    def computation_success(self, task_thread):
        self.success_callback(task_thread.result, self._get_time_spent())

    def computation_failure(self, task_thread):
        logger_msg = self.comp_failed_warning
        if task_thread.error_msg:
            logger_msg += " " + task_thread.error_msg
        logger.warning(logger_msg)
        self.error_callback(task_thread.error_msg)

    def _get_time_spent(self):
        try:
            return self.end_time - self.start_time
        except TypeError:
            logger.error("Cannot measure execution time")

    def __prepare_resources(self):

        self.test_task_res_path = get_test_task_path(self.root_path)
        if not os.path.exists(self.test_task_res_path):
            os.makedirs(self.test_task_res_path)
        else:
            shutil.rmtree(self.test_task_res_path, True)
            os.makedirs(self.test_task_res_path)

        self.test_task_res_dir = get_test_task_path(self.root_path)
        if self.use_task_resources:
            rh = TaskResourceHeader(self.test_task_res_dir)
            res_file = self.task.get_resources(rh, resource_types["zip"], self.tmp_dir)

            if res_file:
                decompress_dir(self.test_task_res_path, res_file)
        for res in self.additional_resources:
            shutil.copy(res, self.test_task_res_path)

        return True

    def __prepare_tmp_dir(self):
        self.tmp_dir = get_test_task_tmp_path(self.root_path)
        if os.path.exists(self.tmp_dir):
            shutil.rmtree(self.tmp_dir, True)
        os.makedirs(self.tmp_dir)

    def _get_task_thread(self, ctd):
        return DockerTaskThread(self,
                                ctd.subtask_id,
                                ctd.docker_images,
                                ctd.working_directory,
                                ctd.src_code,
                                ctd.extra_data,
                                ctd.short_description,
                                self.test_task_res_path,
                                self.tmp_dir,
                                0,
                                check_mem=self.check_mem)
