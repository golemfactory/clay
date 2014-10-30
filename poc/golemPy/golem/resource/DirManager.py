import os
import logging
import shutil

logger = logging.getLogger(__name__)

def splitPath( path ):
    head, tail = os.path.split( path )
    if not tail:
        return []
    if not head:
        return [ tail ]
    return splitPath( head ) + [ tail ]

class DirManager:
    ######################
    def __init__( self, rootPath, nodeId, tmp = 'tmp', res = 'resources', output = 'output' ):
        self.rootPath = rootPath
        self.nodeId = nodeId
        self.tmp = tmp
        self.res = res
        self.output = output

    ######################
    def clearDir( self, dir ):
        for i in os.listdir( dir ):
            path = os.path.join( dir, i )
            if os.path.isfile( path ):
                os.remove( path )
            if os.path.isdir( path ):
                shutil.rmtree( path )

    ######################
    def createDir( self, fullPath ):
        if os.path.exists( fullPath ):
            os.remove( fullPath )

        os.makedirs( fullPath )

    ######################
    def getDir( self, fullPath, create, errMsg ):
        if os.path.isdir( fullPath ):
            return fullPath
        elif create:
            self.createDir( fullPath )
            return fullPath
        else:
            logger.error( errMsg )
            return ""

    ######################
    def getTaskTemporaryDir( self, taskId, create = True ):
        fullPath = self.__getTmpPath( taskId )
        return self.getDir( fullPath, create, "temporary dir does not exist" )

    ######################
    def getTaskResourceDir( self, taskId, create = True ):
        fullPath = self.__getResPath( taskId )
        return self.getDir( fullPath, create, "resource dir does not exist" )

    ######################
    def getTaskOutputDir( self, taskId, create = True ):
        fullPath = self.__getOutPath( taskId )
        return self.getDir( fullPath, create, "output dir does not exist" )

    ######################
    def clearTemporary( self, taskId ):
        self.clearDir( self.__getTmpPath( taskId ) )

    ######################
    def clearResource( self, taskId ):
        self.clearDir( self.__getResPath( taskId ) )

    def clearOutput( self, taskId ):
        self.clearDir( self.__getOutPath( taskId ) )

    ######################
    def __getTmpPath( self, taskId ):
        return os.path.join( self.rootPath, self.nodeId, taskId, self.tmp )

    def __getResPath( self, taskId ):
        return os.path.join( self.rootPath, self.nodeId, taskId, self.res )

    def __getOutPath( self, taskId ):
        return os.path.join( self.rootPath, self.nodeId, taskId, self.output )