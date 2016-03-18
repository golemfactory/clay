import abc
import os
import uuid
import time

from threading import Lock
from golem.core.fileencrypt import FileEncryptor
from .resultpackage import EncryptingTaskResultPackager


class TaskResultPackageManager(object):

    __metaclass__ = abc.ABCMeta

    def __init__(self, resource_manager):
        self.resource_manager = resource_manager

    @abc.abstractmethod
    def create(self, node, task_result):
        pass

    @abc.abstractmethod
    def extract(self, path):
        pass


class EncryptedResultPackageManager(TaskResultPackageManager):

    package_class = EncryptingTaskResultPackager
    lock = Lock()

    def __init__(self, resource_manager):
        super(EncryptedResultPackageManager, self).__init__(resource_manager)
        self.pending_results = {}

    def gen_secret(self):
        return FileEncryptor.gen_secret(12, 24)

    # Using a temp path
    def pull_package(self, multihash, task_id, subtask_id, key_or_secret,
                     success, error):

        filename = str(uuid.uuid4())
        path = self.resource_manager.get_temporary_path(filename, task_id)

        def success_wrapper(*args, **kwargs):
            extracted_pkg = self.extract(path, key_or_secret)
            self._remove_pending_result(subtask_id)
            os.remove(path)
            success(extracted_pkg, multihash, task_id, subtask_id)

        def error_wrapper(*args, **kwargs):
            error(multihash, task_id)

        self._add_pending_result(subtask_id, task_id, path, multihash)
        self.resource_manager.pull_resource(filename,
                                            multihash,
                                            task_id,
                                            success=success_wrapper,
                                            error=error_wrapper)

    def create(self, node, task_result, key_or_secret):

        task_id = task_result.task_id
        out_name = task_id + "." + task_result.subtask_id
        out_path = self.resource_manager.get_resource_path(out_name, task_id)

        if os.path.exists(out_path):
            package = out_path
        else:
            packager = self.package_class(key_or_secret)
            package = packager.create(out_path, node, task_result)

        self.resource_manager.add_resource(package, task_id)
        files = self.resource_manager.list_resources(task_id)

        for file_obj in files:
            name = file_obj if isinstance(file_obj, basestring) else file_obj[0]
            if os.path.basename(name) == out_name:
                return file_obj

        return None

    def extract(self, path, key_or_secret):
        packager = self.package_class(key_or_secret)
        return packager.extract(path)

    def _add_pending_result(self, subtask_id, task_id, path, multihash):
        with self.lock:
            self.pending_results[subtask_id] = [task_id, path, multihash, time.time()]

    def _remove_pending_result(self, subtask_id):
        with self.lock:
            self.pending_results.pop(subtask_id)
