import os
from threading import Thread, Lock
import shutil
import logging

from golem.task.TaskBase import Task
from golem.resource.Resource import TaskResourceHeader, decompress_dir
from golem.task.TaskComputer import PyTestTaskThread

from examples.gnr.RenderingDirManager import get_test_task_path, get_test_task_directory, get_test_task_tmp_path

logger = logging.getLogger(__name__)

class TaskTester:
    #########################
    def __init__(self, task, root_path, finished_callback):
        assert isinstance(task, Task)
        self.task               = task
        self.test_task_res_path    = None
        self.tmp_dir             = None
        self.success            = False
        self.lock               = Lock()
        self.tt                 = None
        self.root_path           = root_path
        self.finished_callback   = finished_callback

    #########################
    def run(self):
        try:
            success = self.__prepare_resources()
            self.__prepare_tmp_dir()

            if not success:
                return False

            ctd = self.task.query_extra_data_for_test_task()


            self.tt = PyTestTaskThread( self,
                                ctd.subtask_id,
                                ctd.working_directory,
                                ctd.src_code,
                                ctd.extra_data,
                                ctd.short_description,
                                self.test_task_res_path,
                                self.tmp_dir,
                                0)
            self.tt.start()

        except Exception as exc:
            logger.warning("Task not tested properly: {}".format(exc))
            self.finished_callback(False)

    #########################
    def increase_request_trust(self, subtask_id):
        pass

    #########################
    def get_progress(self):
        if self.tt:
            with self.lock:
                if self.tt.get_error():
                    logger.warning("Task not tested properly")
                    self.finished_callback(False)
                    return 0
                return self.tt.get_progress()
        return None

    #########################
    def __prepare_resources(self):

        self.test_task_res_path = get_test_task_path(self.root_path)
        if not os.path.exists(self.test_task_res_path):
            os.makedirs(self.test_task_res_path)
        else:
            shutil.rmtree(self.test_task_res_path, True)
            os.makedirs(self.test_task_res_path)

        self.test_taskResDir = get_test_task_directory()
        rh = TaskResourceHeader(self.test_taskResDir)
        res_file = self.task.prepare_resource_delta(self.task.header.task_id, rh)

        if res_file:
            decompress_dir(self.test_task_res_path, res_file)

        return True
    #########################
    def __prepare_tmp_dir(self):

        self.tmp_dir = get_test_task_tmp_path(self.root_path)
        if not os.path.exists(self.tmp_dir):
            os.makedirs(self.tmp_dir)
        else:
            shutil.rmtree(self.tmp_dir, True)
            os.makedirs(self.tmp_dir)

    ###########################
    def task_computed(self, task_thread):
        if task_thread.result:
            res, est_mem = task_thread.result
        if task_thread.result and 'data' in res and res['data']:
            logger.info("Test task computation success !")
            self.finished_callback(True, est_mem)
        else:
            logger.warning("Test task computation failed !!!")
            self.finished_callback(False)