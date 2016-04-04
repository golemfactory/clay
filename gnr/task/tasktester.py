import logging
import os
import shutil
from threading import Lock

from gnr.task.localcomputer import LocalComputer

from golem.core.fileshelper import find_file_with_ext
from golem.docker.task_thread import DockerTaskThread
from golem.task.taskbase import Task, resource_types
from golem.task.taskcomputer import PyTestTaskThread
from golem.resource.resource import TaskResourceHeader, decompress_dir

from gnr.renderingdirmanager import get_test_task_path, get_test_task_directory, get_tmp_path, get_test_task_tmp_path

logger = logging.getLogger(__name__)


class TaskTester(LocalComputer):
    TESTER_WARNING = "Task not tested properly"

    def __init__(self, task, root_path, finished_callback):
        LocalComputer.__init__(self, task, root_path, finished_callback, task.query_extra_data_for_test_task, True,
                               TaskTester.TESTER_WARNING)

    def _get_task_thread(self, ctd):
        if ctd.docker_images:
            return LocalComputer._get_task_thread(self, ctd)
        else:
            return PyTestTaskThread(self,
                                    ctd.subtask_id,
                                    ctd.working_directory,
                                    ctd.src_code,
                                    ctd.extra_data,
                                    ctd.short_description,
                                    self.test_task_res_path,
                                    self.tmp_dir,
                                    0)

    def task_computed(self, task_thread):
        if task_thread.result:
            res, est_mem = task_thread.result
        if task_thread.result and res and res.get("data"):
            logger.info("Test task computation success!")
            
            # Search for flm - the result of testing a lux task
            # It's needed for verification of received results
            flm = find_file_with_ext(self.tmp_dir, [".flm"])
            if flm is not None:
                try:
                    filename = "test_result.flm"
                    flm_path = os.path.join(self.tmp_dir, filename)
                    os.rename(flm, flm_path)
                    save_path = get_tmp_path(self.task.header.node_name, self.task.header.task_id, self.task.root_path)
                    if not os.path.exists(save_path):
                        os.makedirs(save_path)
                    
                    shutil.copy(flm_path, save_path)
                except: 
                    logger.warning("Couldn't rename and copy .flm file")

            self.finished_callback(True, est_mem)
        else:
            logger_msg = "Test task computation failed!"
            if task_thread.error_msg:
                logger_msg += " " + task_thread.error_msg
            logger.warning(logger_msg)
            self.finished_callback(False, error=task_thread.error_msg)


