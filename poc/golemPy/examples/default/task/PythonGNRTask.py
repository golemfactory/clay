from examples.gnr.task.GNRTask import GNRTaskBuilder, GNRTask
from golem.environments.Environment import Environment
from golem.task.TaskBase import ComputeTaskDef
from golem.task.TaskState import SubtaskStatus

import logging
import random

logger = logging.getLogger(__name__)


class PythonGNRTaskBuilder( GNRTaskBuilder ):
    #######################
    def build( self ):
        srcCode = open( self.taskDefinition.mainProgramFile ).read()
        self.taskDefinition.taskResources = set()

        resourceSize = 0
        for resource in self.taskDefinition.taskResources:
            resourceSize += os.stat(resource).st_size

        return PythonGNRTask(    srcCode,
                            self.clientId,
                            self.taskDefinition.taskId,
                            "",
                            0,
                            Environment.getId(),
                            self.taskDefinition.fullTaskTimeout,
                            self.taskDefinition.subtaskTimeout,
                            resourceSize,
                            0,
                            self.taskDefinition.totalSubtasks,
                            self.rootPath
                           )

class PythonGNRTask( GNRTask ):
    #####################
    def __init__( self, srcCode, clientId, taskId, ownerAddress, ownerPort, environment,
                  ttl, subtaskTtl, resourceSize, estimatedMemory, totalTasks, rootPath ):

        GNRTask.__init__( self, srcCode, clientId, taskId,ownerAddress, ownerPort, environment, ttl, subtaskTtl,
                  resourceSize, estimatedMemory )

        self.totalTasks = totalTasks
        self.rootPath = rootPath



    def queryExtraData( self, perfIndex, numCores = 1, clientId = None ):
        ctd = ComputeTaskDef()
        ctd.taskId = self.header.taskId
        hash = "{}".format( random.getrandbits(128) )
        ctd.subtaskId = hash
        ctd.extraData = { "startTask" : self.lastTask,
                          "endTask": self.lastTask + 1 }
        ctd.returnAddress = self.header.taskOwnerAddress
        ctd.returnPort = self.header.taskOwnerPort
        ctd.shortDescription = "Golem update"
        ctd.srcCode = self.srcCode
        ctd.performance = perfIndex
        if self.lastTask + 1 <= self.totalTasks:
            self.lastTask += 1

        self.subTasksGiven[ hash ] = ctd.extraData
        self.subTasksGiven[ hash ][ 'status' ] = SubtaskStatus.starting
        self.subTasksGiven[ hash ][ 'clientId' ] = clientId

        return ctd

    #######################
    def shortExtraDataRepr( self, perfIndex ):
        return "Generic Python Task"
    #######################

    #######################
    def computationFinished( self, subtaskId, taskResult, dirManager = None ):
        self.subTasksGiven[ subtaskId ][ 'status' ] = SubtaskStatus.finished
        self.numTasksReceived += 1

