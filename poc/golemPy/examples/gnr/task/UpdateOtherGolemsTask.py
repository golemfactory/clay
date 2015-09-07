from golem.environments.Environment import Environment
from golem.task.TaskBase import ComputeTaskDef
from golem.task.TaskState import SubtaskStatus

from GNRTask import GNRTask, GNRTaskBuilder

import random
import logging
import os

logger = logging.getLogger(__name__)

##############################################
class UpdateOtherGolemsTaskDefinition:
    def __init__(self):
        self.taskId = ""

        self.fullTaskTimeout    = 0
        self.subtaskTimeout     = 0

        self.resourceDir        = ""
        self.srcFile            = ""
        self.resources          = []
        self.totalSubtasks      = 1

##############################################
class UpdateOtherGolemsTaskBuilder(GNRTaskBuilder):
    #######################
    def __init__(self, client_id, taskDefinition, root_path, srcDir):
        GNRTaskBuilder.__init__(self, client_id, taskDefinition, root_path)
        self.srcDir = srcDir

    def build(self):
        with open(self.taskDefinition.srcFile) as f:
            srcCode = f.read()
        self.taskDefinition.taskResources = set()
        for dir, dirs, files in os.walk(self.srcDir):
            for file_ in files:
                _, ext = os.path.splitext(file_)
                if ext in '.ini':
                    continue
                self.taskDefinition.taskResources.add(os.path.join(dir,file_))

        print self.taskDefinition.taskResources
        resourceSize = 0
        for resource in self.taskDefinition.taskResources:
            resourceSize += os.stat(resource).st_size

        return UpdateOtherGolemsTask(   srcCode,
                            self.client_id,
                            self.taskDefinition.taskId,
                            "",
                            0,
                            "",
                            self.root_path,
                            Environment.getId(),
                            self.taskDefinition.fullTaskTimeout,
                            self.taskDefinition.subtaskTimeout,
                            self.taskDefinition.taskResources,
                            resourceSize,
                            0,
                            self.taskDefinition.totalSubtasks
                          )

##############################################
class UpdateOtherGolemsTask(GNRTask):

    def __init__(self,
                  srcCode,
                  client_id,
                  taskId,
                  ownerAddress,
                  ownerPort,
                  ownerKeyId,
                  root_path,
                  environment,
                  ttl,
                  subtaskTtl,
                  resources,
                  resourceSize,
                  estimatedMemory,
                  totalTasks):


        GNRTask.__init__(self, srcCode, client_id, taskId, ownerAddress, ownerPort, ownerKeyId, environment,
                            ttl, subtaskTtl, resourceSize, estimatedMemory)

        self.totalTasks = totalTasks
        self.root_path = root_path

        self.taskResources = resources
        self.active = True
        self.updated = {}


    #######################
    def abort (self):
        self.active = False

    #######################
    def queryExtraData(self, perfIndex, num_cores, client_id):

        if client_id in self.updated:
            return None

        ctd = ComputeTaskDef()
        ctd.taskId = self.header.taskId
        hash = "{}".format(random.getrandbits(128))
        ctd.subtaskId = hash
        ctd.extraData = { "startTask" : self.lastTask,
                          "endTask": self.lastTask + 1 }
        ctd.returnAddress = self.header.taskOwnerAddress
        ctd.returnPort = self.header.taskOwnerPort
        ctd.taskOwner = self.header.taskOwner
        ctd.shortDescription = "Golem update"
        ctd.srcCode = self.srcCode
        ctd.performance = perfIndex
        if self.lastTask + 1 <= self.totalTasks:
            self.lastTask += 1
        self.updated[ client_id ] = True

        self.subTasksGiven[ hash ] = ctd.extraData
        self.subTasksGiven[ hash ][ 'status' ] = SubtaskStatus.starting
        self.subTasksGiven[ hash ][ 'client_id' ] = client_id

        return ctd

    #######################
    def computationFinished(self, subtaskId, taskResult, dirManager = None, resultType = 0):
        self.subTasksGiven[ subtaskId ][ 'status' ] = SubtaskStatus.finished
