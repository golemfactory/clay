from GNRTask import GNRTask
from GNREnv import GNREnv
from golem.task.TaskBase import ComputeTaskDef, TaskBuilder
from golem.core.simpleauth import SimpleAuth
from golem.resource.Resource import prepareDeltaZip
from golem.manager.client.NodesManagerClient import NodesManagerClient
import cPickle as pickle

import os
import random
import logging

logger = logging.getLogger(__name__)

class InfoTaskBuilder( TaskBuilder ):
    #######################
    def __init__( self, clientId, filePath, managerAddress, managerPort, iterations, fullTaskTimeout, subtaskTimeout ):
        self.clientId = clientId
        self.filePath = filePath
        self.srcFile = open( filePath, "r" )
        self.srcCode = self.srcFile.read()
        self.managerAddress = managerAddress
        self.managerPort = managerPort
        self.iterations = iterations
        self.fullTaskTimeout = fullTaskTimeout
        self.subtaskTimeout = subtaskTimeout

    def build( self ):
        resSize = os.stat(self.filePath)
        resSize = resSize.st_size
        resources = [ os.path.join( os.getcwd(), self.filePath ) ]
        return InfoTask( self.srcCode,
                            self.clientId,
                            "{}".format( SimpleAuth.generateUUID() ),
                            "",
                            0,
                            self.fullTaskTimeout,
                            self.subtaskTimeout,
                            resSize,
                            resources,
                            self.managerAddress,
                            self.managerPort,
                            self.iterations
                           )


class InfoTask( GNRTask ):

    def __init__( self,
                  srcCode,
                  clientId,
                  taskId,
                  ownerAddress,
                  ownerPort,
                  ttl,
                  subtaskTtl,
                  resourceSize,
                  resources,
                  nodesManagerAddress,
                  nodesManagerPort,
                  iterations ):

        GNRTask.__init__( self, srcCode, clientId, taskId, ownerAddress, ownerPort, ttl, subtaskTtl, resourceSize )

        self.estimatedMemory = 0
        self.taskResources = resources
        self.rootPath = os.getcwd()
        self.lastTask = 0
        self.totalTasks = iterations

        self.nodesManagerClient = NodesManagerClient( nodesManagerAddress, int( nodesManagerPort ) )
        self.nodesManagerClient.start()

    def restart( self ):
        self.lastTask = 0

    def abort ( self ):
        self.nodesManagerClient.dropConnection()

    def initialize( self ):
        pass

    def queryExtraData( self, perfIndex, numCores ):
        ctd = ComputeTaskDef()
        ctd.taskId = self.header.taskId
        hash = "{}".format( random.getrandbits(128) )
        ctd.subtaskId = hash
        ctd.extraData = {
                          "startTask" : self.lastTask,
                          "endTask": self.lastTask + 1 }
        ctd.returnAddress = self.header.taskOwnerAddress
        ctd.returnPort = self.header.taskOwnerPort
        ctd.shortDescription = ""
        ctd.srcCode = self.srcCode
        ctd.performance = perfIndex
        if self.lastTask + 1 <= self.totalTasks:
            self.lastTask += 1

        return ctd


   #######################
    def shortExtraDataRepr( self, perfIndex ):
        return self.queryExtraData( perfIndex, 0 )

    #######################
    def needsComputation( self ):
        return self.lastTask != self.totalTasks
    #######################
    def computationStarted( self, extraData ):
        pass

    #######################
    def computationFinished( self, subtaskId, taskResult, dirManager = None):
        try:
            msgs = pickle.loads( taskResult )
            for msg in msgs:
                self.nodesManagerClient.sendClientStateSnapshot( msg )
        except Exception as ex:
            logger.error("Error while interpreting results: {}".format( str( ex ) ) )

    def finishedComputation( self ):
        return self.lastTask == self.totalTasks

    #######################
    def getTotalTasks( self ):
        return self.totalTasks

    #######################
    def getTotalChunks( self ):
        return self.totalTasks

    #######################
    def getActiveTasks( self ):
        return self.lastTask

    #######################
    def getActiveChunks( self ):
        return self.lastTask

    #######################
    def getChunksLeft( self ):
        return self.totalTasks - self.lastTask

    #######################
    def getProgress( self ):
        return float( self.lastTask ) / self.totalTasks

    #######################
    def acceptResultsDelay( self ):
        return 0.0

    #######################
    def prepareResourceDelta( self, taskId, resourceHeader ):
        commonPathPrefix = os.path.commonprefix( self.taskResources )
        commonPathPrefix = os.path.dirname( commonPathPrefix )
        dirName = commonPathPrefix #os.path.join( "res", self.header.clientId, self.header.taskId, "resources" )
        tmpDir = GNREnv.getTmpPath(self.header.clientId, self.header.taskId, self.rootPath)

        if not os.path.exists( tmpDir ):
            os.makedirs( tmpDir )

        if os.path.exists( dirName ):
            return prepareDeltaZip( dirName, resourceHeader, tmpDir, self.taskResources )
        else:
            return None


    #######################
    def testTask( self ):
        return False