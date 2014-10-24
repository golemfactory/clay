from golem.task.TaskBase import Task, TaskHeader, TaskBuilder
from golem.resource.Resource import prepareDeltaZip
from golem.core.Compress import decompress

import OpenEXR, Imath
from PIL import Image, ImageChops

from GNREnv import GNREnv

import pickle
import os
import logging
import subprocess

logger = logging.getLogger(__name__)

class GNRTaskBuilder( TaskBuilder ):
    #######################
    def __init__( self, clientId, taskDefinition, rootPath ):
        self.taskDefinition = taskDefinition
        self.clientId       = clientId
        self.rootPath       = rootPath

    def build( self ):
        pass


class GNRSubtask():
    def __init__(self, subtaskId, startChunk, endChunk):
        self.subtaskId = subtaskId
        self.startChunk = startChunk
        self.endChunk = endChunk

class GNRTask( Task ):
    #####################
    def __init__( self, srcCode, clientId, taskId, ownerAddress, ownerPort, environment, ttl, subtaskTtl, resourceSize ):
        Task.__init__( self, TaskHeader( clientId, taskId, ownerAddress, ownerPort, environment, ttl, subtaskTtl, resourceSize ), srcCode )

    #######################
    def initialize( self ):
        pass

    #######################
    def restart ( self ):
        self.numTasksReceived = 0
        self.lastTask = 0
        self.subTasksGiven.clear()

        self.numFailedSubtasks = 0
        self.failedSubtasks.clear()
        self.header.lastChecking = time.time()
        self.header.ttl = self.fullTaskTimeout

        del self.collector
        self.collector = PbrtTaksCollector()
        self.collectedFileNames = []

        self.previewFilePath = None



    #######################
    def getChunksLeft( self ):
        return (self.totalTasks - self.lastTask) + self.numFailedSubtasks

    #######################
    def getProgress( self ):
        return float( self.lastTask ) / self.totalTasks

    #####################
    def getPreviewFilePath( self ):
        return self.previewFilePath

    #######################
    def subtaskFailed( self, subtaskId, startChunk, endChunk ):
        self.numFailedSubtasks += 1
        self.failedSubtasks.add( GNRSubtask( subtaskId, startChunk, endChunk ) )

    #######################
    def needsComputation( self ):
        return (self.lastTask != self.totalTasks) or (self.numFailedSubtasks > 0)

    #######################
    def finishedComputation( self ):
        return self.numTasksReceived == self.totalTasks

    #######################
    def computationStarted( self, extraData ):
        pass


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
    def prepareResourceDelta( self, taskId, resourceHeader ):
        if taskId == self.header.taskId:
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
        else:
            return None

    #######################
    def abort ( self ):
        pass