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


class TaskComputer(object):
    """ TaskComputer is responsible for task computations that take place in Golem application. Tasks are started
    in separete threads.
    """
    def __init__(self, client_uid, task_server):
        """ Create new task computer instance
        :param client_uid:
        :param task_server:
        :return:
        """
        self.client_uid = client_uid
        self.task_server = task_server
        self.waiting_for_task = None
        self.counting_task = False
        self.current_computations = []
        self.lock = Lock()
        self.last_task_request = time.time()
        self.task_request_frequency = task_server.config_desc.task_request_interval
        self.use_waiting_ttl = task_server.config_desc.use_waiting_for_task_timeout
        self.waiting_for_task_timeout = task_server.config_desc.waiting_for_task_timeout
        self.waiting_ttl = 0
        self.last_checking = time.time()
        self.dir_manager = DirManager(task_server.get_task_computer_root(), self.client_uid)

        self.resource_manager = ResourcesManager(self.dir_manager, self)

        self.assigned_subtasks = {}
        self.task_to_subtask_mapping = {}
        self.max_assigned_tasks = 1

        self.delta = None

    def task_given(self, ctd, subtask_timeout):
        if ctd.subtaskId not in self.assigned_subtasks:
            self.assigned_subtasks[ctd.subtaskId] = ctd
            self.assigned_subtasks[ctd.subtaskId].timeout = subtask_timeout
            self.task_to_subtask_mapping[ctd.taskId] = ctd.subtaskId
            self.__request_resource(ctd.taskId, self.resource_manager.getResourceHeader(ctd.taskId), ctd.returnAddress,
                                    ctd.returnPort, ctd.keyId, ctd.taskOwner)
            return True
        else:
            return False

    def resource_given(self, taskId):
        if taskId in self.task_to_subtask_mapping:
            subtaskId = self.task_to_subtask_mapping[taskId]
            if subtaskId in self.assigned_subtasks:
                self.waiting_ttl = 0
                self.counting_task = True
                self.__compute_task(subtaskId, self.assigned_subtasks[subtaskId].srcCode,
                                    self.assigned_subtasks[subtaskId].extraData,
                                    self.assigned_subtasks[subtaskId].shortDescription,
                                    self.assigned_subtasks[subtaskId].timeout)
                self.waiting_for_task = None
                return True
            else:
                return False

    def task_resource_collected(self, taskId):
        if taskId in self.task_to_subtask_mapping:
            subtaskId = self.task_to_subtask_mapping[taskId]
            if subtaskId in self.assigned_subtasks:
                self.waiting_ttl = 0
                self.counting_task = True
                self.taskTimeout = self.assigned_subtasks[subtaskId].timeout
                self.lastTaskTimeoutChecking = time.time()
                self.task_server.unpack_delta(self.dir_manager.getTaskResourceDir(taskId), self.delta, taskId)
                self.__compute_task(subtaskId, self.assigned_subtasks[subtaskId].srcCode,
                                    self.assigned_subtasks[subtaskId].extraData,
                                    self.assigned_subtasks[subtaskId].shortDescription,
                                    self.assigned_subtasks[subtaskId].timeout)
                self.waiting_for_task = None
                self.delta = None
                return True
            else:
                return False

    def waitForResources(self, taskId, delta):
        if taskId in self.task_to_subtask_mapping:
            subtaskId = self.task_to_subtask_mapping[taskId]
            if subtaskId in self.assigned_subtasks:
                self.delta = delta

    def taskRequestRejected(self, taskId, reason):
        self.waiting_for_task = None
        logger.warning("Task {} request rejected: {}".format(taskId, reason))

    def resourceRequestRejected(self, subtaskId, reason):
        self.waiting_for_task = None
        self.waiting_ttl = 0
        logger.warning("Task {} resource request rejected: {}".format(subtaskId, reason))
        del self.assigned_subtasks[subtaskId]

    def task_computed(self, taskThread):
        with self.lock:
            self.counting_task = False
            if taskThread in self.current_computations:
                self.current_computations.remove(taskThread)

            subtaskId = taskThread.subtaskId

            subtask = self.assigned_subtasks.get(subtaskId)
            if subtask:
                del self.assigned_subtasks[subtaskId]
            else:
                logger.error("No subtask with id {}".format(subtaskId))
                return

            if taskThread.error:
                self.task_server.send_task_failed(subtaskId, subtask.taskId, taskThread.errorMsg,
                                                  subtask.returnAddress, subtask.returnPort, subtask.keyId,
                                                  subtask.taskOwner, self.client_uid)
            elif taskThread.result and 'data' in taskThread.result and 'resultType' in taskThread.result:
                logger.info("Task {} computed".format(subtaskId))
                self.task_server.send_results(subtaskId, subtask.taskId, taskThread.result, subtask.returnAddress,
                                              subtask.returnPort, subtask.keyId, subtask.taskOwner, self.client_uid)
            else:
                self.task_server.send_task_failed(subtaskId, subtask.taskId, "Wrong result format",
                                                  subtask.returnAddress, subtask.returnPort, subtask.keyId,
                                                  subtask.taskOwner, self.client_uid)

    def run(self):

        if self.counting_task:
            for taskThread in self.current_computations:
                taskThread.checkTimeout()
            return

        if self.waiting_for_task == 0 or self.waiting_for_task is None:
            if time.time() - self.last_task_request > self.task_request_frequency:
                if len(self.current_computations) == 0:
                    self.last_task_request = time.time()
                    self.__request_task()
        elif self.use_waiting_ttl:
            time_ = time.time()
            self.waiting_ttl -= time_ - self.last_checking
            self.last_checking = time_
            if self.waiting_ttl < 0:
                self.waiting_for_task = None
                self.waiting_ttl = 0

    def getProgresses(self):
        ret = {}
        for c in self.current_computations:
            tcss = TaskChunkStateSnapshot(c.get_subtask_id(), 0.0, 0.0, c.getProgress(),
                                          c.getTaskShortDescr())  # FIXME: cpu power and estimated time left
            ret[c.subtaskId] = tcss

        return ret

    def change_config(self):
        self.dir_manager = DirManager(self.task_server.get_task_computer_root(), self.client_uid)
        self.resource_manager = ResourcesManager(self.dir_manager, self)
        self.task_request_frequency = self.task_server.config_desc.task_request_interval
        self.use_waiting_ttl = self.task_server.config_desc.use_waiting_for_task_timeout
        self.waiting_for_task_timeout = self.task_server.config_desc.waiting_for_task_timeout

    def sessionTimeout(self):
        if self.counting_task:
            return
        else:
            self.waiting_for_task = None
            self.waiting_ttl = 0

    def increase_request_trust(self, subtaskId):
        with self.lock:
            self.increaseTrustVal = True

    def __request_task(self):
        self.waiting_ttl = self.waiting_for_task_timeout
        self.last_checking = time.time()
        self.waiting_for_task = self.task_server.request_task()

    def __request_resource(self, taskId, resourceHeader, returnAddress, returnPort, keyId, taskOwner):
        self.waiting_ttl = self.waiting_for_task_timeout
        self.last_checking = time.time()
        self.waiting_for_task = 1
        self.waiting_for_task = self.task_server.request_resource(taskId, resourceHeader, returnAddress, returnPort,
                                                                  keyId,
                                                                  taskOwner)

    def __compute_task(self, subtaskId, srcCode, extraData, shortDescr, taskTimeout):
        taskId = self.assigned_subtasks[subtaskId].taskId
        workingDirectory = self.assigned_subtasks[subtaskId].workingDirectory
        self.dir_manager.clearTemporary(taskId)
        tt = PyTaskThread(self, subtaskId, workingDirectory, srcCode, extraData, shortDescr,
                          self.resource_manager.getResourceDir(taskId), self.resource_manager.getTemporaryDir(taskId),
                          taskTimeout)
        self.current_computations.append(tt)
        tt.start()


class AssignedSubTask(object):
    def __init__(self, srcCode, extraData, shortDescr, ownerAddress, ownerPort):
        self.srcCode = srcCode
        self.extraData = extraData
        self.shortDescr = shortDescr
        self.ownerAddress = ownerAddress
        self.ownerPort = ownerPort


class TaskThread(Thread):
    def __init__(self, task_computer, subtaskId, workingDirectory, srcCode, extraData, shortDescr, resPath, tmpPath,
                 timeout=0):
        super(TaskThread, self).__init__()

        self.task_computer = task_computer
        self.vm = None
        self.subtaskId = subtaskId
        self.srcCode = srcCode
        self.extraData = extraData
        self.shortDescr = shortDescr
        self.result = None
        self.done = False
        self.resPath = resPath
        self.tmpPath = tmpPath
        self.workingDirectory = workingDirectory
        self.prevWorkingDirectory = ""
        self.lock = Lock()
        self.error = False
        self.errorMsg = ""
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

    def get_subtask_id(self):
        return self.subtaskId

    def getTaskShortDescr(self):
        return self.shortDescr

    def getProgress(self):
        with self.lock:
            return self.vm.getProgress()

    def getError(self):
        with self.lock:
            return self.error

    def run(self):
        logger.info("RUNNING ")
        try:
            self.__do_work()
            self.task_computer.task_computed(self)
        except Exception as exc:
            logger.error("Task computing error: {}".format(exc))
            self.error = True
            self.errorMsg = str(exc)
            self.done = True
            self.task_computer.task_computed(self)

    def endComp(self):
        self.vm.endComp()

    def __do_work(self):
        extraData = copy(self.extraData)

        absResPath = os.path.abspath(os.path.normpath(self.resPath))
        absTmpPath = os.path.abspath(os.path.normpath(self.tmpPath))

        self.prevWorkingDirectory = os.getcwd()
        os.chdir(os.path.join(absResPath, os.path.normpath(self.workingDirectory)))
        try:
            extraData["resourcePath"] = absResPath
            extraData["tmpPath"] = absTmpPath
            self.result = self.vm.runTask(self.srcCode, extraData)
        finally:
            os.chdir(self.prevWorkingDirectory)


class PyTaskThread(TaskThread):
    def __init__(self, task_computer, subtaskId, workingDirectory, srcCode, extraData, shortDescr, resPath, tmpPath,
                 timeout):
        super(PyTaskThread, self).__init__(task_computer, subtaskId, workingDirectory, srcCode, extraData, shortDescr,
                                           resPath, tmpPath, timeout)
        self.vm = PythonProcVM()


class PyTestTaskThread(PyTaskThread):
    def __init__(self, task_computer, subtaskId, workingDirectory, srcCode, extraData, shortDescr, resPath, tmpPath,
                 timeout):
        super(PyTestTaskThread, self).__init__(task_computer, subtaskId, workingDirectory, srcCode, extraData,
                                               shortDescr, resPath, tmpPath, timeout)
        self.vm = PythonTestVM()
