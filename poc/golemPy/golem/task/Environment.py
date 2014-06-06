import os

class TaskComputerEnvironment:
    ######################
    def __init__( self, rootDir, nodeId ):
        self.rootDir = rootDir
        self.nodeId = nodeId

    ######################
    def reset( self ):
        for i in os.listdir( self.rootDir ):
            os.remove( i )
        
    ######################
    def getTaskTemporaryDir( self, taskId ):
        return self.__createTempraryDir( taskId )

    ######################
    def getTaskResourceDir( self, taskId ):
        return self.__createResourceDir( taskId )

    ######################
    def clearTemporary( self, taskId ):
        tmpDir = self.getTaskTemporaryDir( taskId )

        for i in os.listdir( tmpDir ):
            os.remove( os.path.join( tmpDir, i ) )

    ######################
    def clearResource( self, taskId ):
        resDir = self.getTaskResourceDir( taskId )

        for i in os.listdir( resDir ):
            os.remove( os.path.join( resDir, i ) )

    ######################
    def __createResourceDir( self, taskId ):
        fullPath = os.path.join( self.rootDir, self.nodeId, taskId, "resources" )

        if os.path.exists( fullPath ) and os.path.isdir( fullPath ):
            return fullPath

        if os.path.exists( fullPath ):
            os.remove( fullPath )

        os.makedirs( fullPath )

        return fullPath

    ######################
    def __createTempraryDir( self, taskId ):
        fullPath = os.path.join( self.rootDir, self.nodeId, taskId, "tmp" )

        if os.path.exists( fullPath ) and os.path.isdir( fullPath ):
            return fullPath

        if os.path.exists( fullPath ):
            os.remove( fullPath )

        os.makedirs( fullPath )

        return fullPath


class TaskManagerEnvironment:
    ######################
    def __init__( self, rootDir, nodeId ):
        self.rootDir = rootDir
        self.nodeId = nodeId
        
    ######################
    def getTaskTemporaryDir( self, taskId ):
        return self.__createTempraryDir( taskId )

    ######################
    def getTaskResourceDir( self, taskId ):

        fullPath = os.path.join( self.rootDir, self.nodeId, taskId, "resources" )

        if os.path.exists( fullPath ) and os.path.isdir( fullPath ):
            return fullPath

        print "resource dir does not exist"
        return ""

    ######################
    def getTaskOutputDir( self, taskId ):

        fullPath = os.path.join( self.rootDir, self.nodeId, taskId, "output" )

        if os.path.exists( fullPath ) and os.path.isdir( fullPath ):
            return fullPath

        print "output dir does not exist"
        return ""

    ######################
    def clearTemporary( self, taskId ):

        tmpDir = self.getTaskTemporaryDir( taskId )

        for i in os.listdir( tmpDir ):
            os.remove( os.path.join( tmpDir, i ) )

    ######################
    def __createTempraryDir( self, taskId ):
        fullPath = os.path.join( self.rootDir, self.nodeId, taskId, "tmp" )

        if os.path.exists( fullPath ) and os.path.isdir( fullPath ):
            return fullPath

        if os.path.exists( fullPath ):
            os.remove( fullPath )

        os.makedirs( fullPath )

        return fullPath
    