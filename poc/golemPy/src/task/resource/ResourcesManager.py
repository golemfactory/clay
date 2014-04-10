from Resource import TaskResource, TaskResourceHeader, prepareDeltaZip, decompressDir

import os
from os.path import join, isdir, isfile
import struct

class ResourcesManager:
    ###################
    def __init__( self, taskEnvironment, owner ):
        self.resources          = {}
        self.taskEnvironment    = taskEnvironment
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

        print "Getting resource for delta dir: {} header:{}".format( dirName, resourceHeader )

        if os.path.exists( dirName ):
            taskResHeader = TaskResource.buildDeltaFromHeader( resourceHeader, dirName )
        else:
            taskResHeader = TaskResource( "resources" )

        print  "Getting resource for delta dir: {} header:{} FINISHED".format( dirName, resourceHeader )
        return taskResHeader

    ###################
    def prepareResourceDelta( self, taskId, resourceHeader ):

        dirName = self.getResourceDir( taskId )

        if os.path.exists( dirName ):
            return prepareDeltaZip( dirName, resourceHeader )
        else:
            return ""

    ###################
    def updateResource( self, taskId, resource ):

        dirName = self.getResourceDir( taskId )

        resource.extract( dirName )

    ###################
    def getResourceDir( self, taskId ):
        return self.taskEnvironment.getTaskResourceDir( taskId )

    ###################
    def getTemporaryDir( self, taskId ):
        return self.taskEnvironment.getTaskTemporaryDir( taskId )

    ###################
    def getOutputDir( self, taskId ):
        return self.taskEnvironment.getTaskOutputDir( taskId )


    def fileDataReceived( self, taskId, data ):

        print "\rFile data receving {}%                              ".format( 100 * self.recvSize / float( self.fileSize ) ),

        locData = data
        if self.fileSize == -1:
            # First chunk
            ( self.fileSize, ) = struct.unpack( "!L", data[0:4] )
            print "File size {}".format( self.fileSize )
            locData = data[ 4: ]
            assert self.fh is None

            self.fh = open( os.path.join( self.getTemporaryDir( taskId ),  "res" + taskId ), 'wb' )

        assert self.fh

        self.fh.write( locData )
        self.recvSize += len( locData )

        if self.recvSize == self.fileSize:
            self.fileMode = False
            self.fh.close()
            self.fh = None
            decompressDir( self.getResourceDir(), os.path.join( self.getTemporaryDir( taskId ),  "res" + taskId) )
            owner.resourceGiven( taskId )
            
