import random
import logging
import cPickle as pickle

from golem.manager.client.NodesManagerClient import NodesManagerClient
from golem.environments.Environment import Environment
from golem.task.TaskBase import ComputeTaskDef, resultTypes
from GNRTask import GNRTask, GNRTaskBuilder

logger = logging.getLogger(__name__)

##############################################
class InfoTaskDefinition:
    def __init__( self ):
        self.taskId = ""

        self.fullTaskTimeout    = 0
        self.subtaskTimeout     = 0

        self.srcFile            = ""
        self.totalSubtasks      = 0

        self.managerAddress     = ""
        self.managerPort        = 0

##############################################
class InfoTaskBuilder( GNRTaskBuilder ):

    def build( self ):
        srcCode = open( self.taskDefinition.srcFile ).read()
        return InfoTask(    srcCode,
                            self.clientId,
                            self.taskDefinition.taskId,
                            "",
                            0,
                            Environment.getId(),
                            self.taskDefinition.fullTaskTimeout,
                            self.taskDefinition.subtaskTimeout,
                            0,
                            0,
                            self.taskDefinition.managerAddress,
                            self.taskDefinition.managerPort,
                            self.taskDefinition.totalSubtasks
                           )

##############################################
class InfoTask( GNRTask ):

    def __init__( self,
                  srcCode,
                  clientId,
                  taskId,
                  ownerAddress,
                  ownerPort,
                  environment,
                  ttl,
                  subtaskTtl,
                  resourceSize,
                  estimatedMemory,
                  nodesManagerAddress,
                  nodesManagerPort,
                  iterations ):


        GNRTask.__init__( self, srcCode, clientId, taskId, ownerAddress, ownerPort, environment,
                            ttl, subtaskTtl, resourceSize, estimatedMemory )

        self.totalTasks = iterations

        self.nodesManagerClient = NodesManagerClient( nodesManagerAddress, int( nodesManagerPort ) )
        self.nodesManagerClient.start()

    #######################
    def abort ( self ):
        self.nodesManagerClient.dropConnection()

    #######################
    def queryExtraData( self, perfIndex, numCores, clientId = None ):
        ctd = ComputeTaskDef()
        ctd.taskId = self.header.taskId
        hash = "{}".format( random.getrandbits(128) )
        ctd.subtaskId = hash
        ctd.extraData = {
                          "startTask" : self.lastTask,
                          "endTask": self.lastTask + 1 }
        ctd.returnAddress = self.header.taskOwnerAddress
        ctd.returnPort = self.header.taskOwnerPort
        ctd.shortDescription = "Standard info Task"
        ctd.srcCode = self.srcCode
        ctd.performance = perfIndex
        if self.lastTask + 1 <= self.totalTasks:
            self.lastTask += 1

        return ctd

    #######################
    def computationFinished( self, subtaskId, taskResult, dirManager = None, resultType = 0):
        if resultType != resultTypes['data']:
            logger.error("Only data result format supported")
            return
        try:
            msgs = pickle.loads( taskResult )
            for msg in msgs:
                self.nodesManagerClient.sendClientStateSnapshot( msg )
        except Exception as ex:
            logger.error("Error while interpreting results: {}".format( str( ex ) ) )

    #######################
    def prepareResourceDelta( self, taskId, resourceHeader ):
        return None
