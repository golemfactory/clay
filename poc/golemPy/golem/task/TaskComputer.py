
import sys
sys.path.append('../manager')

from threading import Thread, Lock
import time
from copy import copy

from golem.vm.vm import PythonProcVM, PythonTestVM, PythonVM
from golem.manager.NodeStateSnapshot import TaskChunkStateSnapshot
from golem.resource.ResourcesManager import ResourcesManager
from golem.resource.DirManager import DirManager

import os
import logging

logger = logging.getLogger(__name__)

class TaskComputer:

    ######################
    def __init__(self, client_uid, task_server):
        self.client_uid              = client_uid
        self.task_server             = task_server
        self.waitingForTask         = None
        self.countingTask           = False
        self.currentComputations    = []
        self.lock                   = Lock()
        self.lastTaskRequest        = time.time()
        self.taskRequestFrequency   = task_server.config_desc.task_request_interval
        self.useWaitingTtl          = task_server.config_desc.use_waiting_for_task_timeout
        self.waiting_for_task_timeout  = task_server.config_desc.waiting_for_task_timeout
        self.waitingTtl             = 0
        self.lastChecking           = time.time()
        self.dirManager             = DirManager (task_server.get_task_computer_root(), self.client_uid)

        self.resourceManager        = ResourcesManager(self.dirManager, self)

        self.assignedSubTasks       = {}
        self.taskToSubTaskMapping   = {}
        self.maxAssignedTasks       = 1
        self.curSrcCode             = ""
        self.curExtraData           = None
        self.curShortDescr          = None

        self.delta = None

    ######################
    def taskGiven(self, ctd, subtaskTimeout):
        if ctd.subtaskId not in self.assignedSubTasks:
            self.assignedSubTasks[ ctd.subtaskId ] = ctd
            self.assignedSubTasks[ ctd.subtaskId ].timeout = subtaskTimeout
            self.taskToSubTaskMapping[ ctd.taskId ] = ctd.subtaskId
            self.__request_resource(ctd.taskId, self.resourceManager.getResourceHeader(ctd.taskId), ctd.returnAddress,
                                   ctd.returnPort, ctd.keyId, ctd.taskOwner)
            return True
        else:
            return False

    ######################
    def resourceGiven(self, taskId):
        if taskId in self.taskToSubTaskMapping:
            subtaskId = self.taskToSubTaskMapping[ taskId ]
            if subtaskId in self.assignedSubTasks:
                self.waitingTtl = 0
                self.countingTask = True
                self.__computeTask(subtaskId, self.assignedSubTasks[ subtaskId ].srcCode, self.assignedSubTasks[ subtaskId ].extraData, self.assignedSubTasks[ subtaskId ].shortDescription, self.assignedSubTasks[subtaskId].timeout)
                self.waitingForTask = None
                return True
            else:
                return False

    ######################
    def taskResourceCollected(self, taskId):
        if taskId in self.taskToSubTaskMapping:
            subtaskId = self.taskToSubTaskMapping[ taskId ]
            if subtaskId in self.assignedSubTasks:
                self.waitingTtl = 0
                self.countingTask = True
                self.taskTimeout = self.assignedSubTasks[ subtaskId ].timeout
                self.lastTaskTimeoutChecking = time.time()
                self.task_server.unpack_delta(self.dirManager.getTaskResourceDir(taskId), self.delta, taskId)
                self.__computeTask(subtaskId, self.assignedSubTasks[ subtaskId ].srcCode, self.assignedSubTasks[ subtaskId ].extraData, self.assignedSubTasks[ subtaskId ].shortDescription, self.assignedSubTasks[subtaskId].timeout )
                self.waitingForTask = None
                self.delta = None
                return True
            else:
                return False

    #####################
    def waitForResources(self, taskId, delta):
        if taskId in self.taskToSubTaskMapping:
            subtaskId = self.taskToSubTaskMapping[ taskId ]
            if subtaskId in self.assignedSubTasks:
                self.delta = delta

    ######################
    def taskRequestRejected(self, taskId, reason):
        self.waitingForTask = None
        logger.warning("Task {} request rejected: {}".format(taskId, reason))

    ######################
    def resourceRequestRejected(self, subtaskId, reason):
        self.waitingForTask = None
        self.waitingTtl = 0
        logger.warning("Task {} resource request rejected: {}".format(subtaskId, reason))
        del self.assignedSubTasks[ subtaskId ]

    ######################
    def taskComputed(self, taskThread):
        with self.lock:
            self.countingTask = False
            if taskThread in self.currentComputations:
                self.currentComputations.remove(taskThread)

            subtaskId   = taskThread.subtaskId

            subtask = self.assignedSubTasks.get(subtaskId)
            if subtask:
                del self.assignedSubTasks[subtaskId]
            else:
                logger.error("No subtask with id {}".format(subtaskId))
                return

            if taskThread.error:
                self.task_server.send_task_failed(subtaskId, subtask.taskId, taskThread.errorMsg,
                                               subtask.returnAddress, subtask.returnPort, subtask.keyId,
                                               subtask.taskOwner, self.client_uid)
            elif taskThread.result and 'data' in taskThread.result and 'resultType' in taskThread.result:
                logger.info ("Task {} computed".format(subtaskId))
                self.task_server.send_results(subtaskId, subtask.taskId, taskThread.result, subtask.returnAddress,
                                            subtask.returnPort, subtask.keyId, subtask.taskOwner, self.client_uid)
            else:
                self.task_server.send_task_failed(subtaskId, subtask.taskId, "Wrong result format",
                                               subtask.returnAddress, subtask.returnPort, subtask.keyId,
                                               subtask.taskOwner, self.client_uid)


    ######################
    def run(self):

        if self.countingTask:
            for taskThread in self.currentComputations:
                taskThread.checkTimeout()
            return

        if self.waitingForTask == 0 or self.waitingForTask is None:
            if time.time() - self.lastTaskRequest > self.taskRequestFrequency:
                if len(self.currentComputations) == 0:
                    self.lastTaskRequest = time.time()
                    self.__request_task()
        elif self.useWaitingTtl:
            time_ = time.time()
            self.waitingTtl -= time_ - self.lastChecking
            self.lastChecking = time_
            if self.waitingTtl < 0:
                self.waitingForTask = None
                self.waitingTtl = 0

    ######################
    def getProgresses(self):
        ret = {}
        for c in self.currentComputations:
            tcss = TaskChunkStateSnapshot(c.getSubTaskId(), 0.0, 0.0, c.getProgress(), c.getTaskShortDescr() ) #FIXME: cpu power and estimated time left
            ret[ c.subtaskId ] = tcss

        return ret

    ######################
    def change_config(self):
        self.dirManager = DirManager(self.task_server.get_task_computer_root(), self.client_uid)
        self.resourceManager = ResourcesManager(self.dirManager, self)
        self.taskRequestFrequency   = self.task_server.config_desc.task_request_interval
        self.useWaitingTtl          = self.task_server.config_desc.use_waiting_for_task_timeout
        self.waiting_for_task_timeout  = self.task_server.config_desc.waiting_for_task_timeout

    ######################
    def sessionTimeout(self):
        if self.countingTask:
            return
        else:
            self.waitingForTask = None
            self.waitingTtl = 0

    ######################
    def increaseRequestTrust(self, subtaskId):
        with self.lock:
            self.increaseTrustVal = True

    ######################
    def __request_task(self):
        self.waitingTtl  = self.waiting_for_task_timeout
        self.lastChecking = time.time()
        self.waitingForTask = self.task_server.request_task()

    ######################
    def __request_resource(self, taskId, resourceHeader, returnAddress, returnPort, keyId, taskOwner):
        self.waitingTtl = self.waiting_for_task_timeout
        self.lastChecking = time.time()
        self.waitingForTask = 1
        self.waitingForTask = self.task_server.request_resource(taskId, resourceHeader, returnAddress, returnPort, keyId,
                                                              taskOwner)

    ######################
    def __computeTask(self, subtaskId, srcCode, extraData, shortDescr, taskTimeout):
        taskId = self.assignedSubTasks[ subtaskId ].taskId
        workingDirectory = self.assignedSubTasks[ subtaskId ].workingDirectory
        self.dirManager.clearTemporary(taskId)
        tt = PyTaskThread(self, subtaskId, workingDirectory, srcCode, extraData, shortDescr, self.resourceManager.getResourceDir(taskId), self.resourceManager.getTemporaryDir(taskId), taskTimeout)
        self.currentComputations.append(tt)
        tt.start()

class AssignedSubTask:
    ######################
    def __init__(self, srcCode, extraData, shortDescr, ownerAddress, ownerPort):
        self.srcCode        = srcCode
        self.extraData      = extraData
        self.shortDescr     = shortDescr
        self.ownerAddress   = ownerAddress
        self.ownerPort      = ownerPort


class TaskThread(Thread):
    ######################
    def __init__(self, task_computer, subtaskId, workingDirectory, srcCode, extraData, shortDescr, resPath, tmpPath, timeout = 0):
        super(TaskThread, self).__init__()

        self.task_computer   = task_computer
        self.vm             = None
        self.subtaskId      = subtaskId
        self.srcCode        = srcCode
        self.extraData      = extraData
        self.shortDescr     = shortDescr
        self.result         = None
        self.done           = False
        self.resPath        = resPath
        self.tmpPath        = tmpPath
        self.workingDirectory = workingDirectory
        self.prevWorkingDirectory = ""
        self.lock           = Lock()
        self.error          = False
        self.errorMsg       = ""
        self.useTimeout = timeout != 0
        self.taskTimeout = timeout
        self.lastTimeChecking = time.time()

    ######################
    def checkTimeout(self):
        if not self.useTimeout:
            return
        time_ = time.time()
        self.taskTimeout -= time_ - self.lastTimeChecking
        self.lastTimeChecking = time_
        if self.taskTimeout < 0:
            self.error = True
            self.errorMsg = "Timeout"
            self.endComp()

    ######################
    def getSubTaskId(self):
        return self.subtaskId

    ######################
    def getTaskShortDescr(self):
        return self.shortDescr

    ######################
    def getProgress(self):
        with self.lock:
            return self.vm.getProgress()

    ######################
    def getError(self):
        with self.lock:
            return self.error

    ######################
    def run(self):
        logger.info("RUNNING ")
        try:
            self.__doWork()
            self.task_computer.taskComputed(self)
        except Exception as exc:
            logger.error("Task computing error: {}".format(exc))
            self.error = True
            self.errorMsg = str(exc)
            self.done = True
            self.task_computer.taskComputed(self)

    ######################
    def endComp(self):
        self.vm.endComp()

    ######################
    def __doWork(self):
        extraData = copy(self.extraData)

        absResPath = os.path.abspath(os.path.normpath(self.resPath))
        absTmpPath = os.path.abspath(os.path.normpath(self.tmpPath))

        self.prevWorkingDirectory = os.getcwd()
        os.chdir(os.path.join(absResPath, os.path.normpath(self.workingDirectory)))
        try:
            extraData[ "resourcePath" ] = absResPath
            extraData[ "tmpPath" ] = absTmpPath
            self.result = self.vm.runTask(self.srcCode, extraData)
        finally:
            os.chdir(self.prevWorkingDirectory)

class PyTaskThread(TaskThread):
    ######################
    def __init__(self, task_computer, subtaskId, workingDirectory, srcCode, extraData, shortDescr, resPath, tmpPath, timeout):
        super(PyTaskThread, self).__init__(task_computer, subtaskId, workingDirectory, srcCode, extraData, shortDescr, resPath, tmpPath, timeout)
        self.vm = PythonProcVM()

class PyTestTaskThread(PyTaskThread):
    ######################
    def __init__(self, task_computer, subtaskId, workingDirectory, srcCode, extraData, shortDescr, resPath, tmpPath, timeout):
        super(PyTestTaskThread, self).__init__(task_computer, subtaskId, workingDirectory, srcCode, extraData, shortDescr, resPath, tmpPath, timeout)
        self.vm = PythonTestVM()