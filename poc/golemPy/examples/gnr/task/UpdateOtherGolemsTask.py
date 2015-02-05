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
    def __init__( self ):
        self.taskId = ""

        self.fullTaskTimeout    = 0
        self.subtaskTimeout     = 0

        self.resourceDir        = ""
        self.srcFile            = ""
        self.resources          = []
        self.totalSubtasks      = 1

##############################################
class UpdateOtherGolemsTaskBuilder( GNRTaskBuilder ):
    #######################
    def __init__(self, clientId, taskDefinition, rootPath, srcDir ):
        GNRTaskBuilder.__init__( self, clientId, taskDefinition, rootPath )
        self.srcDir = srcDir

    def build( self ):
        srcCode = open( self.taskDefinition.srcFile ).read()
        self.taskDefinition.taskResources = set()
        for dir, dirs, files in os.walk( self.srcDir ):
            for file_ in files:
                _, ext = os.path.splitext( file_ )
                if ext in '.ini':
                    continue
                self.taskDefinition.taskResources.add( os.path.join( dir,file_ ) )

        print self.taskDefinition.taskResources
        resourceSize = 0
        for resource in self.taskDefinition.taskResources:
            resourceSize += os.stat(resource).st_size

        return UpdateOtherGolemsTask(    srcCode,
                            self.clientId,
                            self.taskDefinition.taskId,
                            "",
                            0,
                            self.rootPath,
                            Environment.getId(),
                            self.taskDefinition.fullTaskTimeout,
                            self.taskDefinition.subtaskTimeout,
                            self.taskDefinition.taskResources,
                            resourceSize,
                            0,
                            self.taskDefinition.totalSubtasks
                           )

##############################################
class UpdateOtherGolemsTask( GNRTask ):

    def __init__( self,
                  srcCode,
                  clientId,
                  taskId,
                  ownerAddress,
                  ownerPort,
                  rootPath,
                  environment,
                  ttl,
                  subtaskTtl,
                  resources,
                  resourceSize,
                  estimatedMemory,
                  totalTasks ):


        GNRTask.__init__( self, srcCode, clientId, taskId, ownerAddress, ownerPort, environment,
                            ttl, subtaskTtl, resourceSize, estimatedMemory )

        self.totalTasks = totalTasks
        self.rootPath = rootPath

        self.taskResources = resources
        self.active = True
        self.updated = {}


    #######################
    def abort ( self ):
        self.active = False

    #######################
    def queryExtraData( self, perfIndex, numCores, clientId ):

        if clientId in self.updated:
            return None

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
        self.updated[ clientId ] = True

        self.subTasksGiven[ hash ] = ctd.extraData
        self.subTasksGiven[ hash ][ 'status' ] = SubtaskStatus.starting
        self.subTasksGiven[ hash ][ 'clientId' ] = clientId

        return ctd

    #######################
    def computationFinished( self, subtaskId, taskResult, dirManager = None, resultType = 0):
        self.subTasksGiven[ subtaskId ][ 'status' ] = SubtaskStatus.finished
