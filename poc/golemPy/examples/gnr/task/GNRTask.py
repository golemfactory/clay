from golem.task.TaskBase import Task, TaskHeader, TaskBuilder, result_types
from golem.task.TaskState import SubtaskStatus
from golem.resource.Resource import prepareDeltaZip, TaskResourceHeader
from golem.environments.Environment import Environment
from golem.network.p2p.Node import Node
from golem.core.compress import decompress

from examples.gnr.RenderingDirManager import getTmpPath

import os
import logging
import time
import pickle

logger = logging.getLogger(__name__)

##############################################
def checkSubtask_idWrapper(func):
    def checkSubtask_id(*args, **kwargs):
        task = args[0]
        subtask_id = args[1]
        if subtask_id not in task.subTasksGiven:
            logger.error("This is not my subtask {}".format(subtask_id))
            return False
        return func(*args, **kwargs)
    return checkSubtask_id

##############################################
class GNRTaskBuilder(TaskBuilder):
    #######################
    def __init__(self, client_id, taskDefinition, root_path):
        self.taskDefinition = taskDefinition
        self.client_id       = client_id
        self.root_path       = root_path

    #######################
    def build(self):
        pass

##############################################
class GNRSubtask():
    #######################
    def __init__(self, subtask_id, startChunk, endChunk):
        self.subtask_id = subtask_id
        self.startChunk = startChunk
        self.endChunk = endChunk

##############################################
class GNROptions:
    #######################
    def __init__(self):
        self.environment = Environment()

    #######################
    def addToResources(self, resources):
        return resources

    #######################
    def removeFromResources(self, resources):
        return resources

##############################################
class GNRTask(Task):
    #####################
    def __init__(self, srcCode, client_id, task_id, ownerAddress, ownerPort, ownerKeyId, environment,
                  ttl, subtaskTtl, resourceSize, estimatedMemory):
        th = TaskHeader(client_id, task_id, ownerAddress, ownerPort, ownerKeyId, environment, Node(),
                         ttl, subtaskTtl, resourceSize, estimatedMemory)
        Task.__init__(self, th, srcCode)

        self.taskResources = []

        self.totalTasks = 0
        self.lastTask = 0

        self.numTasksReceived = 0
        self.subTasksGiven = {}
        self.numFailedSubtasks = 0

        self.fullTaskTimeout = 2200
        self.countingNodes = {}

        self.resFiles = {}

    #######################
    def initialize(self):
        pass

    #######################
    def restart (self):
        self.numTasksReceived = 0
        self.lastTask = 0
        self.subTasksGiven.clear()

        self.numFailedSubtasks = 0
        self.header.last_checking = time.time()
        self.header.ttl = self.fullTaskTimeout


    #######################
    def getChunksLeft(self):
        return (self.totalTasks - self.lastTask) + self.numFailedSubtasks

    #######################
    def getProgress(self):
        return float(self.lastTask) / self.totalTasks


    #######################
    def needsComputation(self):
        return (self.lastTask != self.totalTasks) or (self.numFailedSubtasks > 0)

    #######################
    def finishedComputation(self):
        return self.numTasksReceived == self.totalTasks

    #######################
    def computationStarted(self, extraData):
        pass

    #######################
    def computationFailed(self, subtask_id):
        self._markSubtaskFailed(subtask_id)

    #######################
    def getTotalTasks(self):
        return self.totalTasks

    #######################
    def getTotalChunks(self):
        return self.totalTasks

    #######################
    def getActiveTasks(self):
        return self.lastTask

    #######################
    def getActiveChunks(self):
        return self.lastTask

    #######################
    def setResFiles(self, resFiles):
        self.resFiles = resFiles

    #######################
    def prepare_resourceDelta(self, task_id, resourceHeader):
        if task_id == self.header.task_id:
            commonPathPrefix, dirName, tmpDir = self.__getTaskDirParams()

            if not os.path.exists(tmpDir):
                os.makedirs(tmpDir)

            if os.path.exists(dirName):
                return prepareDeltaZip(dirName, resourceHeader, tmpDir, self.taskResources)
            else:
                return None
        else:
            return None

    #######################
    def getResourcePartsList(self, task_id, resourceHeader):
        if task_id == self.header.task_id:
            commonPathPrefix, dirName, tmpDir = self.__getTaskDirParams()

            if os.path.exists(dirName):
                deltaHeader, parts = TaskResourceHeader.buildPartsHeaderDeltaFromChosen(resourceHeader, dirName, self.resFiles)
                return deltaHeader, parts
            else:
                return None
        else:
            return None

    #######################
    def __getTaskDirParams(self):
        commonPathPrefix = os.path.commonprefix(self.taskResources)
        commonPathPrefix = os.path.dirname(commonPathPrefix)
        dirName = commonPathPrefix #os.path.join("res", self.header.client_id, self.header.task_id, "resources")
        tmpDir = getTmpPath(self.header.client_id, self.header.task_id, self.root_path)
        if not os.path.exists(tmpDir):
                os.makedirs(tmpDir)

        return commonPathPrefix, dirName, tmpDir

    #######################
    def abort (self):
        pass

    #######################
    def updateTaskState(self, taskState):
        pass

    #######################
    def loadTaskResults(self, taskResult, resultType, tmpDir):
        if resultType == result_types['data']:
            return  [ self._unpackTaskResult(trp, tmpDir) for trp in taskResult ]
        elif resultType == result_types['files']:
            return taskResult
        else:
            logger.error("Task result type not supported {}".format(resultType))
            return []

    #######################
    @checkSubtask_idWrapper
    def verifySubtask(self, subtask_id):
       return self.subTasksGiven[ subtask_id ]['status'] == SubtaskStatus.finished

    #######################
    def verifyTask(self):
        return self.finishedComputation()

    #######################
    @checkSubtask_idWrapper
    def getPriceMod(self, subtask_id):
        return 1

    #######################
    @checkSubtask_idWrapper
    def getTrustMod(self, subtask_id):
        return 1.0

    #######################
    @checkSubtask_idWrapper
    def restartSubtask(self, subtask_id):
        if subtask_id in self.subTasksGiven:
            if self.subTasksGiven[ subtask_id ][ 'status' ] == SubtaskStatus.starting:
                self._markSubtaskFailed(subtask_id)
            elif self.subTasksGiven[ subtask_id ][ 'status' ] == SubtaskStatus.finished :
                self._markSubtaskFailed(subtask_id)
                tasks = self.subTasksGiven[ subtask_id ]['endTask'] - self.subTasksGiven[ subtask_id  ]['startTask'] + 1
                self.numTasksReceived -= tasks

    #######################
    @checkSubtask_idWrapper
    def shouldAccept(self, subtask_id):
        if self.subTasksGiven[ subtask_id ][ 'status' ] != SubtaskStatus.starting:
            return False
        return True

    #######################
    @checkSubtask_idWrapper
    def _markSubtaskFailed(self, subtask_id):
        self.subTasksGiven[ subtask_id ]['status'] = SubtaskStatus.failure
        self.countingNodes[ self.subTasksGiven[ subtask_id ][ 'client_id' ] ] = -1
        self.numFailedSubtasks += 1

    #######################
    def _unpackTaskResult(self, trp, tmpDir):
        tr = pickle.loads(trp)
        with open(os.path.join(tmpDir, tr[ 0 ]), "wb") as fh:
            fh.write(decompress(tr[ 1 ]))
        return os.path.join(tmpDir, tr[0])
