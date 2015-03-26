from Resource import TaskResource, TaskResourceHeader, prepareDeltaZip, decompressDir

import os
from os.path import join, isdir, isfile
import struct
import logging

from golem.core.databuffer import DataBuffer
from golem.core.filesHelper import copyFileTree
from golem.resource.ResourceHash import ResourceHash

logger = logging.getLogger(__name__)

class DistributedResourceManager:
    ###################
    def __init__( self, resourceDir ):
        self.resources = set()
        self.resourceDir = resourceDir
        self.resourceHash = ResourceHash( self.resourceDir )
        self.addResources()

    ###################
    def changeResourceDir( self, resourceDir ):
        self.resourceHash.setResourceDir( resourceDir )
        self.copyResources( resourceDir )
        self.resources = set()
        self.resourceDir = resourceDir
        self.addResources()

    ###################
    def copyResources(self, newResourceDir ):
        copyFileTree( self.resourceDir, newResourceDir )
        filenames = next(os.walk( self.resourceDir ))[2]
        for f in filenames:
            os.remove( os.path.join( self.resourceDir, f ) )

    ###################
    def splitFile( self, fileName, blockSize = 2 ** 20 ):
        resourceHash = ResourceHash( self.resourceDir )
        listFiles = [ os.path.basename(file_) for file_ in resourceHash.splitFile( fileName, blockSize ) ]
        self.resources |= set( listFiles )
        return listFiles

    ###################
    def connectFile ( self, partsList, fileName ):
        resourceHash = ResourceHash( self.resourceDir )
        resList = [ os.path.join( self.resourceDir, p ) for p in partsList ]
        resourceHash.connectFiles( resList, fileName )

    ###################
    def addResources( self ):
        filenames = next(os.walk( self.resourceDir ))[2]
        self.resources = set( filenames )

    ###################
    def checkResource( self, resource):
        resPath = os.path.join( self.resourceDir, os.path.basename( resource ))
        if os.path.isfile( resPath ) and self.resourceHash.getFileHash( resPath ) == resource:
            return True
        else:
            return False

    ###################
    def getResourcePath( self, resource ):
        return os.path.join( self.resourceDir, resource )

#########################################################

class ResourcesManager:
    ###################
    def __init__( self, dirManager, owner ):
        self.resources          = {}
        self.dirManager         = dirManager
        self.fh                 = None
        self.fileSize           = -1
        self.recvSize           = 0
        self.owner              = owner
        self.lastPrct           = 0
        self.buffSize           = 4 * 1024 * 1024
        self.buff               = DataBuffer()

    ###################
    def getResourceHeader( self, taskId ):

        taskResHeader = None

        dirName = self.getResourceDir( taskId )

        if os.path.exists( dirName ):
            taskResHeader = TaskResourceHeader.build( "resources", dirName )
        else:
            taskResHeader = TaskResourceHeader( "resources" )

        return taskResHeader

    ###################
    def getResourceDelta( self, taskId, resourceHeader ):

        dirName = self.getResourceDir( taskId )

        taskResHeader = None

        logger.info( "Getting resource for delta dir: {} header:{}".format( dirName, resourceHeader ) )

        if os.path.exists( dirName ):
            taskResHeader = TaskResource.buildDeltaFromHeader( resourceHeader, dirName )
        else:
            taskResHeader = TaskResource( "resources" )

        logger.info( "Getting resource for delta dir: {} header:{} FINISHED".format( dirName, resourceHeader ) )
        return taskResHeader

    ###################
    def prepareResourceDelta( self, taskId, resourceHeader ):

        dirName = self.getResourceDir( taskId )

        if os.path.exists( dirName ):
            return prepareDeltaZip( dirName, resourceHeader, self.getTemporaryDir( taskId ) )
        else:
            return ""

    ###################
    def updateResource( self, taskId, resource ):

        dirName = self.getResourceDir( taskId )

        resource.extract( dirName )

    ###################
    def getResourceDir( self, taskId ):
        return self.dirManager.getTaskResourceDir( taskId )

    ###################
    def getTemporaryDir( self, taskId ):
        return self.dirManager.getTaskTemporaryDir( taskId )

    ###################
    def getOutputDir( self, taskId ):
        return self.dirManager.getTaskOutputDir( taskId )

            
