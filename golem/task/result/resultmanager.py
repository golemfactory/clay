import abc
import logging
import os

from golem.core.fileencrypt import FileEncryptor
from golem.resource.client import async_run
from golem.resource.client import AsyncRequest
from .resultpackage import EncryptingTaskResultPackager

logger = logging.getLogger(__name__)


class TaskResultPackageManager(object):

    __metaclass__ = abc.ABCMeta

    def __init__(self, resource_manager):
        self.resource_manager = resource_manager

    @abc.abstractmethod
    def create(self, node, task_result, client_options=None, **kwargs):
        pass

    @abc.abstractmethod
    def extract(self, path, output_dir=None, **kwargs):
        pass


class EncryptedResultPackageManager(TaskResultPackageManager):

    min_secret_len = 16
    max_secret_len = 32
    package_class = EncryptingTaskResultPackager

    def __init__(self, resource_manager):
        super(EncryptedResultPackageManager, self).__init__(resource_manager)

    def gen_secret(self):
        return FileEncryptor.gen_secret(self.min_secret_len, self.max_secret_len)

    # Using a temp path
    def pull_package(self, multihash, task_id, subtask_id, key_or_secret,
                     success, error, async=True, client_options=None, output_dir=None):

        file_name = task_id + "." + subtask_id
        file_path = self.resource_manager.storage.get_path(file_name, task_id)
        output_dir = os.path.join(output_dir or os.path.dirname(file_path), subtask_id)

        if os.path.exists(file_path):
            os.remove(file_path)

        def package_downloaded(*args, **kwargs):
            request = AsyncRequest(self.extract, file_path,
                                   output_dir=output_dir,
                                   key_or_secret=key_or_secret)
            async_run(request, package_extracted, error)

        def package_extracted(extracted_pkg, *args, **kwargs):
            success(extracted_pkg, multihash, task_id, subtask_id)
            os.remove(file_path)

        resource = self.resource_manager.wrap_file((file_name, multihash))
        self.resource_manager.pull_resource(resource, task_id,
                                            client_options=client_options,
                                            success=package_downloaded,
                                            error=error,
                                            async=async,
                                            pin=False)

    def create(self, node, task_result, client_options=None, key_or_secret=None):
        if not key_or_secret:
            raise ValueError("Empty key / secret")

        task_id = task_result.task_id
        file_name = task_id + "." + task_result.subtask_id
        file_path = self.resource_manager.storage.get_path(file_name, task_id)

        if os.path.exists(file_path):
            os.remove(file_path)

        packager = self.package_class(key_or_secret)
        path = packager.create(file_path,
                               node=node,
                               task_result=task_result)

        self.resource_manager.add_file(path, task_id,
                                       client_options=client_options)

        for resource in self.resource_manager.get_resources(task_id):
            if resource.contains_file(file_name):
                return file_path, resource.hash

        if os.path.exists(path):
            raise EnvironmentError("Error creating package: 'add' command failed")
        raise Exception("Error creating package: file not found")

    def extract(self, path, output_dir=None, key_or_secret=None, **kwargs):
        if not key_or_secret:
            raise ValueError("Empty key / secret")

        packager = self.package_class(key_or_secret)
        return packager.extract(path, output_dir=output_dir)
