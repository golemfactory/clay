import abc
import logging
import os
import uuid
from threading import Lock

from golem.core.fileencrypt import FileEncryptor
from .resultpackage import EncryptingTaskResultPackager

logger = logging.getLogger(__name__)


class TaskResultPackageManager(object):

    __metaclass__ = abc.ABCMeta

    def __init__(self, resource_manager):
        self.resource_manager = resource_manager

    @abc.abstractmethod
    def create(self, node, task_result, client_options=None):
        pass

    @abc.abstractmethod
    def extract(self, path):
        pass


class EncryptedResultPackageManager(TaskResultPackageManager):

    min_secret_len = 12
    max_secret_len = 24
    package_class = EncryptingTaskResultPackager
    lock = Lock()

    def __init__(self, resource_manager):
        super(EncryptedResultPackageManager, self).__init__(resource_manager)

    def gen_secret(self):
        return FileEncryptor.gen_secret(self.min_secret_len, self.max_secret_len)

    # Using a temp path
    def pull_package(self, multihash, task_id, subtask_id, key_or_secret,
                     success, error, async=True, client_options=None):

        filename = str(uuid.uuid4())
        path = self.resource_manager.get_resource_path(filename, task_id)

        def success_wrapper(*args, **kwargs):
            extracted_pkg = self.extract(path, key_or_secret)
            os.remove(path)
            success(extracted_pkg, multihash, task_id, subtask_id)

        self.resource_manager.pull_resource(filename,
                                            multihash,
                                            task_id,
                                            client_options=client_options,
                                            success=success_wrapper,
                                            error=error,
                                            async=async,
                                            pin=False)

    def create(self, node, task_result, key_or_secret, client_options=None):

        task_id = task_result.task_id
        out_name = task_id + "." + task_result.subtask_id
        out_path = self.resource_manager.get_resource_path(out_name, task_id)

        if os.path.exists(out_path):
            os.remove(out_path)

        packager = self.package_class(key_or_secret)
        package = packager.create(out_path, node, task_result)

        self.resource_manager.add_resource(package, task_id, client_options=client_options)
        files = self.resource_manager.list_resources(task_id)

        for file_obj in files:
            name = file_obj if isinstance(file_obj, basestring) else file_obj[0]
            if os.path.basename(name) == out_name:
                return file_obj

        if os.path.exists(package):
            raise EnvironmentError("Error creating package: 'add' command failed")
        raise Exception("Error creating package: file not found")

    def extract(self, path, key_or_secret, *args):
        packager = self.package_class(key_or_secret)
        return packager.extract(path)
