from Resource import TaskResource, TaskResourceHeader

import os
from os.path import join, isdir, isfile

class ResourcesManager:
    ###################
    def __init__( self, taskEnvironment ):
        self.resources      = {}
        self.taskEnvironment = taskEnvironment

    ###################
    def getResourceHeader( self, taskId ):

        taskResHeader = None

        dirName = self.taskEnvironment.getResourceDir( taskId )

        if os.path.exists( dirName ):
            taskResHeader = TaskResourceHeader.build( dirName )
        else:
            taskResHeader = TaskResourceHeader( dirName, dirName )

        return taskResHeader

    ###################
    def getResourceDelta( self, taskId, resourceHeader ):

        curDir = os.getcwd()

        dirName = taskId

        os.chdir( self.resourcesDir )

        taskResHeader = None

        if os.path.exists( dirName ):
            taskResHeader = TaskResource.buildDeltaFromHeader( resourceHeader, dirName )
        else:
            taskResHeader = TaskResource( dirName, dirName )

        os.chdir( curDir )

        return taskResHeader

    ###################
    def updateResource( self, taskId, resource ):

        curDir = os.getcwd()

        dirName = taskId

        os.chdir( self.resourcesDir )

        resource.extract( dirName )

        os.chdir( curDir )
