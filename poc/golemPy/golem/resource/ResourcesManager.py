from Resource import TaskResource, TaskResourceHeader, prepareDeltaZip, decompressDir

import os
from os.path import join, isdir, isfile
import struct
import logging

from golem.core.databuffer import DataBuffer
from golem.core.fileshelper import copy_file_tree
from golem.resource.ResourceHash import ResourceHash

logger = logging.getLogger(__name__)

class DistributedResourceManager:
    ###################
    def __init__(self, resourceDir):
        self.resources = set()
        self.resourceDir = resourceDir
        self.resourceHash = ResourceHash(self.resourceDir)
        self.addResources()

    ###################
    def change_resource_dir(self, resourceDir):
        self.resourceHash.setResourceDir(resourceDir)
        self.copyResources(resourceDir)
        self.resources = set()
        self.resourceDir = resourceDir
        self.addResources()

    ###################
    def copyResources(self, newResourceDir):
        copy_file_tree(self.resourceDir, newResourceDir)
        filenames = next(os.walk(self.resourceDir))[2]
        for f in filenames:
            os.remove(os.path.join(self.resourceDir, f))

    ###################
    def splitFile(self, fileName, blockSize = 2 ** 20):
        resourceHash = ResourceHash(self.resourceDir)
        listFiles = [ os.path.basename(file_) for file_ in resourceHash.splitFile(fileName, blockSize) ]
        self.resources |= set(listFiles)
        return listFiles

    ###################
    def connectFile (self, partsList, fileName):
        resourceHash = ResourceHash(self.resourceDir)
        resList = [ os.path.join(self.resourceDir, p) for p in partsList ]
        resourceHash.connectFiles(resList, fileName)

    ###################
    def addResources(self):
        filenames = next(os.walk(self.resourceDir))[2]
        self.resources = set(filenames)

    ###################
    def check_resource(self, resource):
        resPath = os.path.join(self.resourceDir, os.path.basename(resource))
        if os.path.isfile(resPath) and self.resourceHash.getFileHash(resPath) == resource:
            return True
        else:
            return False

    ###################
    def getResourcePath(self, resource):
        return os.path.join(self.resourceDir, resource)

#########################################################

class ResourcesManager:
    ###################
    def __init__(self, dir_manager, owner):
        self.resources          = {}
        self.dir_manager         = dir_manager
        self.fh                 = None
        self.fileSize           = -1
        self.recvSize           = 0
        self.owner              = owner
        self.lastPrct           = 0
        self.buffSize           = 4 * 1024 * 1024
        self.buff               = DataBuffer()

    ###################
    def getResourceHeader(self, task_id):

        taskResHeader = None

        dirName = self.get_resource_dir(task_id)

        if os.path.exists(dirName):
            taskResHeader = TaskResourceHeader.build("resources", dirName)
        else:
            taskResHeader = TaskResourceHeader("resources")

        return taskResHeader

    ###################
    def getResourceDelta(self, task_id, resourceHeader):

        dirName = self.get_resource_dir(task_id)

        taskResHeader = None

        logger.info("Getting resource for delta dir: {} header:{}".format(dirName, resourceHeader))

        if os.path.exists(dirName):
            taskResHeader = TaskResource.buildDeltaFromHeader(resourceHeader, dirName)
        else:
            taskResHeader = TaskResource("resources")

        logger.info("Getting resource for delta dir: {} header:{} FINISHED".format(dirName, resourceHeader))
        return taskResHeader

    ###################
    def prepare_resourceDelta(self, task_id, resourceHeader):

        dirName = self.get_resource_dir(task_id)

        if os.path.exists(dirName):
            return prepareDeltaZip(dirName, resourceHeader, self.getTemporaryDir(task_id))
        else:
            return ""

    ###################
    def updateResource(self, task_id, resource):

        dirName = self.get_resource_dir(task_id)

        resource.extract(dirName)

    ###################
    def get_resource_dir(self, task_id):
        return self.dir_manager.get_task_resource_dir(task_id)

    ###################
    def getTemporaryDir(self, task_id):
        return self.dir_manager.get_task_temporary_dir(task_id)

    ###################
    def getOutputDir(self, task_id):
        return self.dir_manager.get_task_output_dir(task_id)

            
