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
        if ctd.subtask_id not in self.assigned_subtasks:
            self.assigned_subtasks[ctd.subtask_id] = ctd
            self.assigned_subtasks[ctd.subtask_id].timeout = subtask_timeout
            self.task_to_subtask_mapping[ctd.task_id] = ctd.subtask_id
            self.__request_resource(ctd.task_id, self.resource_manager.getResourceHeader(ctd.task_id), ctd.returnAddress,
                                    ctd.returnPort, ctd.keyId, ctd.taskOwner)
            return True
        else:
            return False

    def resource_given(self, task_id):
        if task_id in self.task_to_subtask_mapping:
            subtask_id = self.task_to_subtask_mapping[task_id]
            if subtask_id in self.assigned_subtasks:
                self.waiting_ttl = 0
                self.counting_task = True
                self.__compute_task(subtask_id, self.assigned_subtasks[subtask_id].srcCode,
                                    self.assigned_subtasks[subtask_id].extraData,
                                    self.assigned_subtasks[subtask_id].shortDescription,
                                    self.assigned_subtasks[subtask_id].timeout)
                self.waiting_for_task = None
                return True
            else:
                return False

    def task_resource_collected(self, task_id):
        if task_id in self.task_to_subtask_mapping:
            subtask_id = self.task_to_subtask_mapping[task_id]
            if subtask_id in self.assigned_subtasks:
                self.waiting_ttl = 0
                self.counting_task = True
                self.taskTimeout = self.assigned_subtasks[subtask_id].timeout
                self.lastTaskTimeoutChecking = time.time()
                self.task_server.unpack_delta(self.dir_manager.getTaskResourceDir(task_id), self.delta, task_id)
                self.__compute_task(subtask_id, self.assigned_subtasks[subtask_id].srcCode,
                                    self.assigned_subtasks[subtask_id].extraData,
                                    self.assigned_subtasks[subtask_id].shortDescription,
                                    self.assigned_subtasks[subtask_id].timeout)
                self.waiting_for_task = None
                self.delta = None
                return True
            else:
                return False

    def waitForResources(self, task_id, delta):
        if task_id in self.task_to_subtask_mapping:
            subtask_id = self.task_to_subtask_mapping[task_id]
            if subtask_id in self.assigned_subtasks:
                self.delta = delta

    def taskRequestRejected(self, task_id, reason):
        self.waiting_for_task = None
        logger.warning("Task {} request rejected: {}".format(task_id, reason))

    def resourceRequestRejected(self, subtask_id, reason):
        self.waiting_for_task = None
        self.waiting_ttl = 0
        logger.warning("Task {} resource request rejected: {}".format(subtask_id, reason))
        del self.assigned_subtasks[subtask_id]

    def task_computed(self, taskThread):
        with self.lock:
            self.counting_task = False
            if taskThread in self.current_computations:
                self.current_computations.remove(taskThread)

            subtask_id = taskThread.subtask_id

            subtask = self.assigned_subtasks.get(subtask_id)
            if subtask:
                del self.assigned_subtasks[subtask_id]
            else:
                logger.error("No subtask with id {}".format(subtask_id))
                return

            if taskThread.error:
                self.task_server.send_task_failed(subtask_id, subtask.task_id, taskThread.errorMsg,
                                                  subtask.returnAddress, subtask.returnPort, subtask.keyId,
                                                  subtask.taskOwner, self.client_uid)
            elif taskThread.result and 'data' in taskThread.result and 'resultType' in taskThread.result:
                logger.info("Task {} computed".format(subtask_id))
                self.task_server.send_results(subtask_id, subtask.task_id, taskThread.result, subtask.returnAddress,
                                              subtask.returnPort, subtask.keyId, subtask.taskOwner, self.client_uid)
            else:
                self.task_server.send_task_failed(subtask_id, subtask.task_id, "Wrong result format",
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
            ret[c.subtask_id] = tcss

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

    def increase_request_trust(self, subtask_id):
        with self.lock:
            self.increaseTrustVal = True

    def __request_task(self):
        self.waiting_ttl = self.waiting_for_task_timeout
        self.last_checking = time.time()
        self.waiting_for_task = self.task_server.request_task()

    def __request_resource(self, task_id, resourceHeader, returnAddress, returnPort, keyId, taskOwner):
        self.waiting_ttl = self.waiting_for_task_timeout
        self.last_checking = time.time()
        self.waiting_for_task = 1
        self.waiting_for_task = self.task_server.request_resource(task_id, resourceHeader, returnAddress, returnPort,
                                                                  keyId,
                                                                  taskOwner)

    def __compute_task(self, subtask_id, srcCode, extraData, shortDescr, taskTimeout):
        task_id = self.assigned_subtasks[subtask_id].task_id
        workingDirectory = self.assigned_subtasks[subtask_id].workingDirectory
        self.dir_manager.clearTemporary(task_id)
        tt = PyTaskThread(self, subtask_id, workingDirectory, srcCode, extraData, shortDescr,
                          self.resource_manager.getResourceDir(task_id), self.resource_manager.getTemporaryDir(task_id),
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
    def __init__(self, task_computer, subtask_id, workingDirectory, srcCode, extraData, shortDescr, resPath, tmpPath,
                 timeout=0):
        super(TaskThread, self).__init__()

        self.task_computer = task_computer
        self.vm = None
        self.subtask_id = subtask_id
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
        return self.subtask_id

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
    def __init__(self, task_computer, subtask_id, workingDirectory, srcCode, extraData, shortDescr, resPath, tmpPath,
                 timeout):
        super(PyTaskThread, self).__init__(task_computer, subtask_id, workingDirectory, srcCode, extraData, shortDescr,
                                           resPath, tmpPath, timeout)
        self.vm = PythonProcVM()


class PyTestTaskThread(PyTaskThread):
    def __init__(self, task_computer, subtask_id, workingDirectory, srcCode, extraData, shortDescr, resPath, tmpPath,
                 timeout):
        super(PyTestTaskThread, self).__init__(task_computer, subtask_id, workingDirectory, srcCode, extraData,
                                               shortDescr, resPath, tmpPath, timeout)
        self.vm = PythonTestVM()
