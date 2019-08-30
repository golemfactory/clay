import logging

import abc
import os

from golem.core import golem_async
from golem.core.fileencrypt import FileEncryptor
from .resultpackage import (
    EncryptingTaskResultPackager, ExtractedPackage, ZipTaskResultPackager)

logger = logging.getLogger(__name__)


class TaskResultPackageManager(object, metaclass=abc.ABCMeta):

    def __init__(self, resource_manager):
        self.resource_manager = resource_manager

    @abc.abstractmethod
    def create(self, node, task_result, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def extract(self, path, output_dir=None, **kwargs):
        raise NotImplementedError


class EncryptedResultPackageManager(TaskResultPackageManager):

    min_secret_len = 16
    max_secret_len = 32
    package_class = EncryptingTaskResultPackager
    zip_package_class = ZipTaskResultPackager

    def __init__(self, resource_manager):
        super(EncryptedResultPackageManager, self).__init__(resource_manager)

    def gen_secret(self):
        return FileEncryptor.gen_secret(
            self.min_secret_len,
            self.max_secret_len,
        )

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

        def package_downloaded(*args, **kwargs):
            request = golem_async.AsyncRequest(
                self.extract,
                file_path,
                output_dir=output_dir,
                key_or_secret=key_or_secret,
            )
            golem_async.async_run(request, package_extracted, error)

        def package_extracted(extracted_pkg, *args, **kwargs):
            success(extracted_pkg, content_hash, task_id, subtask_id)

        resource = content_hash, [file_name]
        self.resource_manager.pull_resource(resource, task_id,
                                            client_options=client_options,
                                            success=package_downloaded,
                                            error=error,
                                            async_=async_)

    def create(self, task_result, client_options, key_or_secret=None):
        if not key_or_secret:
            raise ValueError("Empty key / secret")

        file_name, encrypted_package_path = self.get_file_name_and_path(
            task_result.task_id, task_result.subtask_id)

        if os.path.exists(encrypted_package_path):
            os.remove(encrypted_package_path)

        packager = self.package_class(key_or_secret)
        path, sha1 = packager.create(
            encrypted_package_path,
            task_result.result,
        )

        package_path = packager.package_name(encrypted_package_path)
        package_size = os.path.getsize(package_path)

        self.resource_manager.add_file(
            path,
            task_result.task_id,
            client_options=client_options)

        for resource in self.resource_manager.get_resources(
                task_result.task_id):
            if file_name in resource.files:
                return (
                    resource.hash,
                    encrypted_package_path,
                    sha1,
                    package_size,
                    package_path
                )

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

    def extract_zip(self, path, output_dir=None) -> ExtractedPackage:
        packager = self.zip_package_class()
        return packager.extract(path, output_dir=output_dir)
