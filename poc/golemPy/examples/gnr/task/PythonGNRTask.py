from examples.gnr.task.GNRTask import GNRTaskBuilder, GNRTask, checkSubtask_idWrapper
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
                            self.taskDefinition.task_id,
                            "",
                            0,
                            "",
                            Environment.getId(),
                            self.taskDefinition.fullTaskTimeout,
                            self.taskDefinition.subtask_timeout,
                            resourceSize,
                            0,
                            self.taskDefinition.totalSubtasks,
                            self.root_path
                          )

class PythonGNRTask(GNRTask):
    #####################
    def __init__(self, srcCode, client_id, task_id, ownerAddress, ownerPort, ownerKeyId, environment,
                  ttl, subtaskTtl, resourceSize, estimated_memory, totalTasks, root_path):

        GNRTask.__init__(self, srcCode, client_id, task_id,ownerAddress, ownerPort, ownerKeyId, environment, ttl, subtaskTtl,
                  resourceSize, estimated_memory)

        self.totalTasks = totalTasks
        self.root_path = root_path



    def queryExtraData(self, perfIndex, num_cores = 1, client_id = None):
        ctd = ComputeTaskDef()
        ctd.task_id = self.header.task_id
        hash = "{}".format(random.getrandbits(128))
        ctd.subtask_id = hash
        ctd.extra_data = { "startTask" : self.lastTask,
                          "endTask": self.lastTask + 1 }
        ctd.returnAddress = self.header.taskOwnerAddress
        ctd.returnPort = self.header.taskOwnerPort
        ctd.taskOnwer = self.header.taskOwner
        ctd.shortDescription = "Golem update"
        ctd.srcCode = self.srcCode
        ctd.performance = perfIndex
        if self.lastTask + 1 <= self.totalTasks:
            self.lastTask += 1

        self.subTasksGiven[ hash ] = ctd.extra_data
        self.subTasksGiven[ hash ][ 'status' ] = SubtaskStatus.starting
        self.subTasksGiven[ hash ][ 'client_id' ] = client_id

        return ctd

    #######################
    def shortExtraDataRepr(self, perfIndex):
        return "Generic Python Task"

    #######################
    @checkSubtask_idWrapper
    def computationFinished(self, subtask_id, taskResult, dir_manager = None, resultType = 0):
        self.subTasksGiven[ subtask_id ][ 'status' ] = SubtaskStatus.finished
        self.numTasksReceived += 1

