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

        dirName = self.getResourceDir( taskId )

        if os.path.exists( dirName ):
            taskResHeader = TaskResourceHeader.build( dirName )
        else:
            taskResHeader = TaskResourceHeader( dirName, dirName )

        return taskResHeader

    ###################
    def getResourceDelta( self, taskId, resourceHeader ):

        dirName = self.getResourceDir( taskId )

        taskResHeader = None

        if os.path.exists( dirName ):
            taskResHeader = TaskResource.buildDeltaFromHeader( resourceHeader, dirName )
        else:
            taskResHeader = TaskResource( dirName, dirName )

        return taskResHeader

    ###################
    def updateResource( self, taskId, resource ):

        dirName = self.getResourceDir( taskId )

        resource.extract( dirName )

    ###################
    def getResourceDir( self, taskId ):
        return self.taskEnvironment.getResourceDir( taskId )

    ###################
    def getTemporatyDir( self, taskId ):
        return self.taskEnvironment.getTemporatyDir( taskId )

    ###################
    def getOutputDir( self, taskId ):
        return self.taskEnvironment.getOutput( taskId )