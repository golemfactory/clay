from Resource import TaskResource, TaskResourceHeader, prepareDeltaZip, decompressDir

import os
from os.path import join, isdir, isfile
import struct
import logging

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

        print "\rFile data receving {}%                              ".format( 100 * self.recvSize / float( self.fileSize ) ),

        locData = data
        if self.fileSize == -1:
            # First chunk
            ( self.fileSize, ) = struct.unpack( "!L", data[0:4] )
            logger.info( "File size {}".format( self.fileSize ) )
            locData = data[ 4: ]
            assert self.fh is None

            self.fh = open( os.path.join( self.getTemporaryDir( taskId ),  "res" + taskId ), 'wb' )

        assert self.fh

        self.fh.write( locData )
        self.recvSize += len( locData )

        if self.recvSize == self.fileSize:
            conn.fileMode = False
            self.fh.close()
            self.fh = None
            if self.fileSize > 0:
                decompressDir( self.getResourceDir( taskId ), os.path.join( self.getTemporaryDir( taskId ),  "res" + taskId) )
            self.owner.resourceGiven( taskId )
            self.fileSize = -1
            self.recvSize = 0
            
