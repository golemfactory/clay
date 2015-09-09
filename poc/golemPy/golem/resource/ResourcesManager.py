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
    def __init__(self, resource_dir):
        self.resources = set()
        self.resource_dir = resource_dir
        self.resourceHash = ResourceHash(self.resource_dir)
        self.add_resources()

    ###################
    def change_resource_dir(self, resource_dir):
        self.resourceHash.set_resource_dir(resource_dir)
        self.copyResources(resource_dir)
        self.resources = set()
        self.resource_dir = resource_dir
        self.add_resources()

    ###################
    def copyResources(self, newResourceDir):
        copy_file_tree(self.resource_dir, newResourceDir)
        filenames = next(os.walk(self.resource_dir))[2]
        for f in filenames:
            os.remove(os.path.join(self.resource_dir, f))

    ###################
    def split_file(self, file_name, blockSize = 2 ** 20):
        resourceHash = ResourceHash(self.resource_dir)
        list_files = [ os.path.basename(file_) for file_ in resourceHash.split_file(file_name, blockSize) ]
        self.resources |= set(list_files)
        return list_files

    ###################
    def connect_file (self, partsList, file_name):
        resourceHash = ResourceHash(self.resource_dir)
        resList = [ os.path.join(self.resource_dir, p) for p in partsList ]
        resourceHash.connect_files(resList, file_name)

    ###################
    def add_resources(self):
        filenames = next(os.walk(self.resource_dir))[2]
        self.resources = set(filenames)

    ###################
    def check_resource(self, resource):
        res_path = os.path.join(self.resource_dir, os.path.basename(resource))
        if os.path.isfile(res_path) and self.resourceHash.getFileHash(res_path) == resource:
            return True
        else:
            return False

    ###################
    def get_resource_path(self, resource):
        return os.path.join(self.resource_dir, resource)

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
    def get_resource_header(self, task_id):

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

            
