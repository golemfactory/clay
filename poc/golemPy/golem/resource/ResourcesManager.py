from Resource import TaskResource, TaskResourceHeader, prepare_delta_zip, decompress_dir

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
        self.resourceHash.set_resource_dir(resourceDir)
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
    def splitFile(self, file_name, blockSize = 2 ** 20):
        resourceHash = ResourceHash(self.resourceDir)
        listFiles = [ os.path.basename(file_) for file_ in resourceHash.splitFile(file_name, blockSize) ]
        self.resources |= set(listFiles)
        return listFiles

    ###################
    def connectFile (self, partsList, file_name):
        resourceHash = ResourceHash(self.resourceDir)
        resList = [ os.path.join(self.resourceDir, p) for p in partsList ]
        resourceHash.connectFiles(resList, file_name)

    ###################
    def addResources(self):
        filenames = next(os.walk(self.resourceDir))[2]
        self.resources = set(filenames)

    ###################
    def check_resource(self, resource):
        res_path = os.path.join(self.resourceDir, os.path.basename(resource))
        if os.path.isfile(res_path) and self.resourceHash.getFileHash(res_path) == resource:
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

        dir_name = self.get_resource_dir(task_id)

        if os.path.exists(dir_name):
            taskResHeader = TaskResourceHeader.build("resources", dir_name)
        else:
            taskResHeader = TaskResourceHeader("resources")

        return taskResHeader

    ###################
    def getResourceDelta(self, task_id, resource_header):

        dir_name = self.get_resource_dir(task_id)

        taskResHeader = None

        logger.info("Getting resource for delta dir: {} header:{}".format(dir_name, resource_header))

        if os.path.exists(dir_name):
            taskResHeader = TaskResource.build_delta_from_header(resource_header, dir_name)
        else:
            taskResHeader = TaskResource("resources")

        logger.info("Getting resource for delta dir: {} header:{} FINISHED".format(dir_name, resource_header))
        return taskResHeader

    ###################
    def prepare_resource_delta(self, task_id, resource_header):

        dir_name = self.get_resource_dir(task_id)

        if os.path.exists(dir_name):
            return prepare_delta_zip(dir_name, resource_header, self.getTemporaryDir(task_id))
        else:
            return ""

    ###################
    def updateResource(self, task_id, resource):

        dir_name = self.get_resource_dir(task_id)

        resource.extract(dir_name)

    ###################
    def get_resource_dir(self, task_id):
        return self.dir_manager.get_task_resource_dir(task_id)

    ###################
    def getTemporaryDir(self, task_id):
        return self.dir_manager.get_task_temporary_dir(task_id)

    ###################
    def getOutputDir(self, task_id):
        return self.dir_manager.get_task_output_dir(task_id)

            
