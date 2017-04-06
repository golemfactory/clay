from resource import TaskResource, TaskResourceHeader, prepare_delta_zip

import os
import logging

from golem.core.databuffer import DataBuffer
from golem.core.fileshelper import copy_file_tree
from golem.resource.resourcehash import ResourceHash

logger = logging.getLogger(__name__)


class DistributedResourceManager:
    def __init__(self, resource_dir):
        self.resources = set()
        self.resource_dir = resource_dir
        self.resource_hash = ResourceHash(self.resource_dir)
        self.add_resources()

    def copy_resources(self, new_resource_dir):
        copy_file_tree(self.resource_dir, new_resource_dir)
        filenames = next(os.walk(self.resource_dir))[2]
        for f in filenames:
            os.remove(os.path.join(self.resource_dir, f))

    def split_file(self, file_name, block_size=2 ** 20):
        resource_hash = ResourceHash(self.resource_dir)
        list_files = [os.path.basename(file_) for file_ in resource_hash.split_file(file_name, block_size)]
        self.resources |= set(list_files)
        return list_files

    def connect_file(self, parts_list, file_name):
        resource_hash = ResourceHash(self.resource_dir)
        res_list = [os.path.join(self.resource_dir, p) for p in parts_list]
        resource_hash.connect_files(res_list, file_name)

    def add_resources(self):
        filenames = next(os.walk(self.resource_dir))[2]
        self.resources = set(filenames)

    def check_resource(self, resource):
        res_path = os.path.join(self.resource_dir, os.path.basename(resource))
        if os.path.isfile(res_path) and self.resource_hash.get_file_hash(res_path) == resource:
            return True
        else:
            return False

    def get_resource_path(self, resource):
        return os.path.join(self.resource_dir, resource)


class ResourcesManager:
    def __init__(self, dir_manager, owner):
        self.resources = {}
        self.dir_manager = dir_manager
        self.fh = None
        self.file_size = -1
        self.recv_size = 0
        self.owner = owner
        self.last_prct = 0
        self.buff_size = 4 * 1024 * 1024
        self.buff = DataBuffer()

    def get_resource_header(self, task_id):

        dir_name = self.get_resource_dir(task_id)

        if os.path.exists(dir_name):
            task_res_header = TaskResourceHeader.build("resources", dir_name)
        else:
            task_res_header = TaskResourceHeader("resources")

        return task_res_header

    def get_resource_delta(self, task_id, resource_header):

        dir_name = self.get_resource_dir(task_id)

        logger.info("Getting resource for delta dir: {} header:{}".format(dir_name, resource_header))

        if os.path.exists(dir_name):
            task_res_header = TaskResource.build_delta_from_header(resource_header, dir_name)
        else:
            task_res_header = TaskResource("resources")

        logger.info("Getting resource for delta dir: {} header:{} FINISHED".format(dir_name, resource_header))
        return task_res_header

    def update_resource(self, task_id, resource):

        dir_name = self.get_resource_dir(task_id)

        resource.extract(dir_name)

    def get_resource_dir(self, task_id):
        return self.dir_manager.get_task_resource_dir(task_id)

    def get_temporary_dir(self, task_id):
        return self.dir_manager.get_task_temporary_dir(task_id)

    def get_output_dir(self, task_id):
        return self.dir_manager.get_task_output_dir(task_id)
