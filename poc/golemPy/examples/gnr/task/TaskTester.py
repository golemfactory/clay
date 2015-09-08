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
        self.testTaskResPath    = None
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

            ctd = self.task.queryExtraDataForTestTask()


            self.tt = PyTestTaskThread( self,
                                ctd.subtask_id,
                                ctd.workingDirectory,
                                ctd.srcCode,
                                ctd.extra_data,
                                ctd.shortDescription,
                                self.testTaskResPath,
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
    def getProgress(self):
        if self.tt:
            with self.lock:
                if self.tt.getError():
                    logger.warning("Task not tested properly")
                    self.finishedCallback(False)
                    return 0
                return self.tt.getProgress()
        return None

    #########################
    def __prepare_resources(self):

        self.testTaskResPath = getTestTaskPath(self.root_path)
        if not os.path.exists(self.testTaskResPath):
            os.makedirs(self.testTaskResPath)
        else:
            shutil.rmtree(self.testTaskResPath, True)
            os.makedirs(self.testTaskResPath)

        self.testTaskResDir = getTestTaskDirectory()
        rh = TaskResourceHeader(self.testTaskResDir)
        resFile = self.task.prepare_resource_delta(self.task.header.task_id, rh)

        if resFile:
            decompress_dir(self.testTaskResPath, resFile)

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
    def task_computed(self, taskThread):
        if taskThread.result:
            res, estMem = taskThread.result
        if taskThread.result and 'data' in res and res['data']:
            logger.info("Test task computation success !")
            self.finishedCallback(True, estMem)
        else:
            logger.warning("Test task computation failed !!!")
            self.finishedCallback(False)