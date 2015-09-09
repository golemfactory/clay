import os
from threading import Thread, Lock
import shutil
import logging

from golem.task.TaskBase import Task
from golem.resource.Resource import TaskResourceHeader, decompress_dir
from golem.task.TaskComputer import PyTestTaskThread

from examples.gnr.RenderingDirManager import getTestTaskPath, getTestTaskDirectory, getTestTaskTmpPath

logger = logging.getLogger(__name__)

class TaskTester:
    #########################
    def __init__(self, task, root_path, finishedCallback):
        assert isinstance(task, Task)
        self.task               = task
        self.test_taskResPath    = None
        self.tmpDir             = None
        self.success            = False
        self.lock               = Lock()
        self.tt                 = None
        self.root_path           = root_path
        self.finishedCallback   = finishedCallback

    #########################
    def run(self):
        try:
            success = self.__prepare_resources()
            self.__prepareTmpDir()

            if not success:
                return False

            ctd = self.task.query_extra_dataForTestTask()


            self.tt = PyTestTaskThread( self,
                                ctd.subtask_id,
                                ctd.working_directory,
                                ctd.src_code,
                                ctd.extra_data,
                                ctd.short_description,
                                self.test_taskResPath,
                                self.tmpDir,
                                0)
            self.tt.start()

        except Exception as exc:
            logger.warning("Task not tested properly: {}".format(exc))
            self.finishedCallback(False)

    #########################
    def increase_request_trust(self, subtask_id):
        pass

    #########################
    def get_progress(self):
        if self.tt:
            with self.lock:
                if self.tt.get_error():
                    logger.warning("Task not tested properly")
                    self.finishedCallback(False)
                    return 0
                return self.tt.get_progress()
        return None

    #########################
    def __prepare_resources(self):

        self.test_taskResPath = getTestTaskPath(self.root_path)
        if not os.path.exists(self.test_taskResPath):
            os.makedirs(self.test_taskResPath)
        else:
            shutil.rmtree(self.test_taskResPath, True)
            os.makedirs(self.test_taskResPath)

        self.test_taskResDir = getTestTaskDirectory()
        rh = TaskResourceHeader(self.test_taskResDir)
        resFile = self.task.prepare_resource_delta(self.task.header.task_id, rh)

        if resFile:
            decompress_dir(self.test_taskResPath, resFile)

        return True
    #########################
    def __prepareTmpDir(self):

        self.tmpDir = getTestTaskTmpPath(self.root_path)
        if not os.path.exists(self.tmpDir):
            os.makedirs(self.tmpDir)
        else:
            shutil.rmtree(self.tmpDir, True)
            os.makedirs(self.tmpDir)

    ###########################
    def task_computed(self, task_thread):
        if task_thread.result:
            res, estMem = task_thread.result
        if task_thread.result and 'data' in res and res['data']:
            logger.info("Test task computation success !")
            self.finishedCallback(True, estMem)
        else:
            logger.warning("Test task computation failed !!!")
            self.finishedCallback(False)