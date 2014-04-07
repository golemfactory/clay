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
    def getTaskResourceDir( self, taksId ):
        return self.__createResourceDir( taskId )

    ######################
    def clearTemporary( self, taksId ):
        for i in os.listdir( self.getTaskTemporaryDir( taskId ) ):
            os.remove( i )

    ######################
    def clearResource( self, taskId ):
        for i in os.listdir( self.getTaskResourceDir( taskId ) ):
            os.remove( i )

    ######################
    def __createResourceDir( self, taskId ):
        fullPath = os.path.join( self.rootDir, taskId, "resources" )

        if os.path.exists( fullPath ) and os.path.isdir( fullPath ):
            return

        if os.path.exists( fullPath ):
            os.remove( fullPath )

        os.makedirs( fullPath )

        return fullPath

    ######################
    def __createTempraryDir( self, taskId ):
        fullPath = os.path.join( self.rootDir, taskId, "tmp" )

        if os.path.exists( fullPath ) and os.path.isdir( fullPath ):
            return

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
    def getTaskResourceDir( self, taksId ):

        fullPath = os.path.join( self.rootDir, taskId, "resources" )

        if os.path.exists( fullPath ) and os.path.isdir( fullPath ):
            print "resource dir does not exist"
            return ""

        return fullPath

    ######################
    def getTaskOutputDir( self, taksId ):

        fullPath = os.path.join( self.rootDir, taskId, "output" )

        if os.path.exists( fullPath ) and os.path.isdir( fullPath ):
            print "output dir does not exist"
            return ""

        return fullPath

    ######################
    def clearTemporary( self, taksId ):
        for i in os.listdir( self.getTaskTemporaryDir( taskId ) ):
            os.remove( i )

    ######################
    def __createTempraryDir( self, taskId ):
        fullPath = os.path.join( self.rootDir, taskId, "tmp" )

        if os.path.exists( fullPath ) and os.path.isdir( fullPath ):
            return

        if os.path.exists( fullPath ):
            os.remove( fullPath )

        os.makedirs( fullPath )

        return fullPath
    