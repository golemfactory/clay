from .resource import TaskResource, TaskResourceHeader

import os
import logging

from golem.core.fileshelper import copy_file_tree
from golem.resource.resourcehash import ResourceHash

logger = logging.getLogger(__name__)


class ResourcesManager:
    def __init__(self, dir_manager, owner):
        self.resources = {}
        self.dir_manager = dir_manager
        self.fh = None
        self.file_size = -1
        self.recv_size = 0
        self.owner = owner
        self.last_prct = 0

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
