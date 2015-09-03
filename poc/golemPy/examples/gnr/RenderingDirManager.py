import os

TEST_RES_DIRECTORY = "testing_task_resources"
TEST_TMP_DIRECTORY = "testing_task_tmp"
RES_DIRECTORY = "res"
TMP_DIRECTORY = "tmp"
PREV_FILE = "ui/nopreview.png"

def getTestTaskDirectory():
    return TEST_RES_DIRECTORY

def getPreviewFile ():
    return PREV_FILE

def getTestTaskPath(rootPath):
    return os.path.join(rootPath, TEST_RES_DIRECTORY)

def getTestTaskTmpPath(rootPath):
    return os.path.join(rootPath, TEST_TMP_DIRECTORY)

def getTmpPath(client_id, taskId, rootPath):
    return os.path.join(rootPath, RES_DIRECTORY, client_id, taskId, TMP_DIRECTORY)