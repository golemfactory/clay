from Resource import TaskResource, TaskResourceHeader

import os
from os.path import join, isdir, isfile

class ResourcesManager:
    ###################
    def __init__( self, resourcesDir ):
        self.resourcesDir   = resourcesDir
        self.resources      = {}

    ###################
    def getResourceHeader( self, taskId ):

        dirName = join( self.resourcesDir, taskId )

        if os.path.exists( join( self.resourcesDir, taskId ) ):
            return TaskResourceHeader.build( dirName )
        else:
            return TaskResourceHeader( dirName, dirName )

    ###################
    def getResourceDelta( self, taskId, resourceHeader ):
        dirName = join( self.resourcesDir, taskId )

        if os.path.exists( join( self.resourcesDir, taskId ) ):
            return TaskResource.buildDeltaFromHeader( resourceHeader, dirName )
        else:
            return TaskResource( dirName, dirName )

    ###################
    def updateResource( self, taskId, resource ):
        dirName = join( self.resourcesDir, taskId )

        resource.extract( dirName )
