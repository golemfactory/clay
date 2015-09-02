import os
import logging
import shutil

from golem.core.simpleexccmd import is_windows

logger = logging.getLogger(__name__)

def splitPath(path):
    head, tail = os.path.split(path)
    if not tail:
        return []
    if not head:
        return [ tail ]
    return splitPath(head) + [ tail ]

class DirManager:
    ######################
    def __init__(self, rootPath, nodeId, tmp = 'tmp', res = 'resources', output = 'output', globalResource = 'golemres'):
        self.rootPath = rootPath
        self.nodeId = nodeId
        self.tmp = tmp
        self.res = res
        self.output = output
        self.globalResource = globalResource
        if is_windows():
            self.__getPath = self.__getPathWindows

    ######################
    def clearDir(self, d):
        if not os.path.isdir(d):
            return
        for i in os.listdir(d):
            path = os.path.join(d, i)
            if os.path.isfile(path):
                os.remove(path)
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)

    ######################
    def createDir(self, fullPath):
        if os.path.exists(fullPath):
            os.remove(fullPath)

        os.makedirs(fullPath)

    ######################
    def getDir(self, fullPath, create, errMsg):
        if os.path.isdir(fullPath):
            return self.__getPath(fullPath)
        elif create:
            self.createDir(fullPath)
            return self.__getPath(fullPath)
        else:
            logger.error(errMsg)
            return ""

    ######################
    def getResourceDir (self, create = True):
        fullPath = self.__getGlobalResourcePath()
        return self.getDir(fullPath, create, "resource dir does not exist")

    ######################
    def getTaskTemporaryDir(self, taskId, create = True):
        fullPath = self.__getTmpPath(taskId)
        return self.getDir(fullPath, create, "temporary dir does not exist")

    ######################
    def getTaskResourceDir(self, taskId, create = True):
        fullPath = self.__getResPath(taskId)
        return self.getDir(fullPath, create, "resource dir does not exist")

    ######################
    def getTaskOutputDir(self, taskId, create = True):
        fullPath = self.__getOutPath(taskId)
        return self.getDir(fullPath, create, "output dir does not exist")

    ######################
    def clearTemporary(self, taskId):
        self.clearDir(self.__getTmpPath(taskId))

    ######################
    def clearResource(self, taskId):
        self.clearDir(self.__getResPath(taskId))

    def clearOutput(self, taskId):
        self.clearDir(self.__getOutPath(taskId))

    ######################
    def __getTmpPath(self, taskId):
        return os.path.join(self.rootPath, self.nodeId, taskId, self.tmp)

    def __getResPath(self, taskId):
        return os.path.join(self.rootPath, self.nodeId, taskId, self.res)

    def __getOutPath(self, taskId):
        return os.path.join(self.rootPath, self.nodeId, taskId, self.output)

    def __getGlobalResourcePath(self):
        return os.path.join(self.rootPath, self.globalResource)

    ######################
    def __getPath(self, path):
        return path

    def __getPathWindows(self, path):
        return path.replace("\\", "/")
