import os

TEST_RES_DIRECTORY = "testing_task_resources"
RES_DIRECTORY = "res"

class GNREnv:

    @classmethod
    def getTestTaskDirectory( cls ):
        return TEST_RES_DIRECTORY


    def __init__(self, rootDir):
        self.rootDir = rootDir
        print rootDir

    def getPreviewPath( self, clientId, taskId):
        return os.path.join( self.rootDir, RES_DIRECTORY, clientId, taskId, "tmp" )