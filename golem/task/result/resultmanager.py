import logging

import abc
import os

from golem.core.async import AsyncRequest, async_run
from golem.core.deferred import sync_wait
from golem.core.fileencrypt import FileEncryptor
from .resultpackage import EncryptingTaskResultPackager, ExtractedPackage

logger = logging.getLogger(__name__)


class TaskResultPackageManager(object, metaclass=abc.ABCMeta):

    def __init__(self, resource_manager):
        self.resource_manager = resource_manager

    @abc.abstractmethod
    def create(self, node, task_result, **kwargs):
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

    def get_file_name_and_path(self, task_id, subtask_id):
        file_name = task_id + "." + subtask_id
        file_path = self.resource_manager.storage.get_path(file_name, task_id)
        return file_name, file_path

    # Using a temp path
    def pull_package(  # noqa pylint:disable=too-many-arguments,too-many-locals
            self, content_hash, task_id, subtask_id, key_or_secret,
            success, error, async_=True, client_options=None, output_dir=None):

        file_name, file_path = self.get_file_name_and_path(task_id, subtask_id)
        output_dir = os.path.join(
            output_dir or os.path.dirname(file_path), subtask_id)

        if os.path.exists(file_path):
            os.remove(file_path)

        def package_downloaded(*_args, **_kwargs):
            request = AsyncRequest(self.extract, file_path,
                                   output_dir=output_dir,
                                   key_or_secret=key_or_secret)
            async_run(request, package_extracted, error)

        def package_extracted(extracted_pkg, *_args, **_kwargs):
            success(extracted_pkg, content_hash, task_id, subtask_id)

        resource = content_hash, [file_name]
        self.resource_manager.pull_resource(
            resource, task_id,
            client_options=client_options,
            async_=async_
        ).addCallbacks(
            package_downloaded,
            lambda t: error(*t)
        )

    def create(self, node, task_result, key_or_secret=None):
        if not key_or_secret:
            raise ValueError("Empty key / secret")

        file_name, file_path = self.get_file_name_and_path(
            task_result.task_id, task_result.subtask_id)

        if os.path.exists(file_path):
            os.remove(file_path)

        packager = self.package_class(key_or_secret)
        path, sha1 = packager.create(file_path,
                                     node=node,
                                     task_result=task_result)

        size = os.path.getsize(path)

        self.resource_manager.add_file(path, task_result.task_id)
        resources = sync_wait(self.resource_manager.get_resources(
            task_result.task_id))

        for resource in resources:
            if file_name in resource.files:
                return resource.hash, file_path, sha1, size

        if os.path.exists(path):
            raise EnvironmentError("Error creating package: "
                                   "'add' command failed")
        raise Exception("Error creating package: file not found")

    def extract(  # noqa: pylint:disable=arguments-differ
            self, path, output_dir=None,
            key_or_secret=None, **kwargs) -> ExtractedPackage:

        if not key_or_secret:
            raise ValueError("Empty key / secret")

        packager = self.package_class(key_or_secret)
        return packager.extract(path, output_dir=output_dir)
