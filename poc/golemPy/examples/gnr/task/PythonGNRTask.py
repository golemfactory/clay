from examples.gnr.task.GNRTask import GNRTaskBuilder, GNRTask, checkSubtaskIdWrapper
from golem.environments.Environment import Environment
from golem.task.TaskBase import ComputeTaskDef
from golem.task.TaskState import SubtaskStatus

import logging
import random

logger = logging.getLogger(__name__)


class PythonGNRTaskBuilder(GNRTaskBuilder):
    #######################
    def build(self):
        with open(self.taskDefinition.mainProgramFile) as f:
            srcCode = f.read()
        self.taskDefinition.taskResources = set()

        resourceSize = 0
        for resource in self.taskDefinition.taskResources:
            resourceSize += os.stat(resource).st_size

        return PythonGNRTask(   srcCode,
                            self.client_id,
                            self.taskDefinition.taskId,
                            "",
                            0,
                            "",
                            Environment.getId(),
                            self.taskDefinition.fullTaskTimeout,
                            self.taskDefinition.subtaskTimeout,
                            resourceSize,
                            0,
                            self.taskDefinition.totalSubtasks,
                            self.root_path
                          )

class PythonGNRTask(GNRTask):
    #####################
    def __init__(self, srcCode, client_id, taskId, ownerAddress, ownerPort, ownerKeyId, environment,
                  ttl, subtaskTtl, resourceSize, estimatedMemory, totalTasks, root_path):

        GNRTask.__init__(self, srcCode, client_id, taskId,ownerAddress, ownerPort, ownerKeyId, environment, ttl, subtaskTtl,
                  resourceSize, estimatedMemory)

        self.totalTasks = totalTasks
        self.root_path = root_path



    def queryExtraData(self, perfIndex, num_cores = 1, client_id = None):
        ctd = ComputeTaskDef()
        ctd.taskId = self.header.taskId
        hash = "{}".format(random.getrandbits(128))
        ctd.subtaskId = hash
        ctd.extraData = { "startTask" : self.lastTask,
                          "endTask": self.lastTask + 1 }
        ctd.returnAddress = self.header.taskOwnerAddress
        ctd.returnPort = self.header.taskOwnerPort
        ctd.taskOnwer = self.header.taskOwner
        ctd.shortDescription = "Golem update"
        ctd.srcCode = self.srcCode
        ctd.performance = perfIndex
        if self.lastTask + 1 <= self.totalTasks:
            self.lastTask += 1

        self.subTasksGiven[ hash ] = ctd.extraData
        self.subTasksGiven[ hash ][ 'status' ] = SubtaskStatus.starting
        self.subTasksGiven[ hash ][ 'client_id' ] = client_id

        return ctd

    #######################
    def shortExtraDataRepr(self, perfIndex):
        return "Generic Python Task"

    #######################
    @checkSubtaskIdWrapper
    def computationFinished(self, subtaskId, taskResult, dirManager = None, resultType = 0):
        self.subTasksGiven[ subtaskId ][ 'status' ] = SubtaskStatus.finished
        self.numTasksReceived += 1

