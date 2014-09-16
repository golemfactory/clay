import os

TEST_RES_DIRECTORY = "testing_task_resources"
TEST_TMP_DIRECTORY = "testing_task_tmp"
RES_DIRECTORY = "res"
PREV_FILE = "ui/nopreview.jpg"

class GNREnv:

    @classmethod
    def getTestTaskDirectory( cls ):
        return TEST_RES_DIRECTORY

    @classmethod
    def getPreviewFile ( cls ):
        return PREV_FILE

    @classmethod
    def getTestTaskPath( cls, rootPath ):
        return os.path.join(rootPath, TEST_RES_DIRECTORY)

    @classmethod
    def getTestTaskTmpPath( cls, rootPath ):
        return os.path.join( rootPath, TEST_TMP_DIRECTORY)

    @classmethod
    def getTmpPath( cls, clientId, taskId, rootPath):
        return os.path.join( rootPath, RES_DIRECTORY, clientId, taskId, "tmp" )