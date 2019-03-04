import logging


logger = logging.getLogger(__name__)


class ResourcesManager:
    def __init__(self, dir_manager):
        self.dir_manager = dir_manager

    def get_resource_dir(self, task_id):
        return self.dir_manager.get_task_resource_dir(task_id)

    def get_temporary_dir(self, task_id):
        return self.dir_manager.get_task_temporary_dir(task_id)

    def get_output_dir(self, task_id):
        return self.dir_manager.get_task_output_dir(task_id)
