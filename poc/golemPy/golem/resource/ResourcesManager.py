from Resource import TaskResource, TaskResourceHeader, prepareDeltaZip, decompressDir

import os
from os.path import join, isdir, isfile
import struct
import logging

from golem.core.databuffer import DataBuffer

logger = logging.getLogger(__name__)

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


    def fileDataReceived( self, taskId, data, conn ):

        prct = int( 100 * self.recvSize / float( self.fileSize ) )
        if prct > self.lastPrct:
            print "\rFile data receving {} %                       ".format(  prct ),
        locData = data
        if self.fileSize == -1:
            # First chunk
            self.lastPrct = 0
            self.buffSize = 0
            ( self.fileSize, ) = struct.unpack( "!L", data[0:4] )
            locData = data[ 4: ]
            assert self.fh is None

            self.fh = open( os.path.join( self.getTemporaryDir( taskId ),  "res" + taskId ), 'wb' )

        assert self.fh
        self.recvSize += len( locData )
        self.buff.appendString( locData )

        if self.buff.dataSize() >= self.buffSize or self.recvSize == self.fileSize:
            self.fh.write( self.buff.readAll() )

        if self.recvSize == self.fileSize:
            conn.fileMode = False
            self.fh.close()
            self.fh = None
            if self.fileSize > 0:
                decompressDir( self.getResourceDir( taskId ), os.path.join( self.getTemporaryDir( taskId ),  "res" + taskId) )
            self.owner.resourceGiven( taskId )
            self.fileSize = -1
            self.recvSize = 0
            
