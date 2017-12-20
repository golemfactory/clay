import logging
import os
from collections import Iterable, Sized

from golem.core.async import AsyncRequest, async_run
from golem.core.fileshelper import common_dir
from golem.network.hyperdrive.client import HyperdriveClient
from golem.resource.client import ClientHandler, DummyClient
from golem.resource.hyperdrive.peermanager import HyperdrivePeerManager
from golem.resource.hyperdrive.resource import Resource, ResourceStorage

logger = logging.getLogger(__name__)


def is_collection(obj):
    return isinstance(obj, Iterable) and isinstance(obj, Sized)


class HyperdriveResourceManager(ClientHandler):

    def __init__(self, dir_manager, daemon_address=None, config=None,
                 resource_dir_method=None):

        super().__init__(config)

        self.dir_manager = dir_manager
        self.client = HyperdriveClient(**self.config.client)
        self.peer_manager = HyperdrivePeerManager(daemon_address)
        self.storage = ResourceStorage(self.dir_manager, resource_dir_method or
                                       dir_manager.get_task_resource_dir)

    @staticmethod
    def build_client_options(peers=None, **kwargs):
        return HyperdriveClient.build_options(peers=peers, **kwargs)

    @staticmethod
    def to_wire(resources):
        iterator = filter(None, resources)
        return list(resource.serialize() for resource in iterator)

    @staticmethod
    def from_wire(serialized):
        iterator = filter(lambda x: is_collection(x)
                          and len(x) > 1, serialized)
        results = [Resource.deserialize(entry) for entry in iterator
                   if is_collection(entry) and len(entry) > 1]

        if len(results) != len(serialized):
            logger.warning("Errors occurred while deserializing %r", serialized)

        return results

    def get_resources(self, task_id):
        return self.storage.get_resources(task_id)

    def add_task(self, files, task_id, resource_hash=None, async=True):
        args = (files, task_id, resource_hash)
        if async:
            return async_run(AsyncRequest(self._add_task, *args))
        return self._add_task(*args)

    def remove_task(self, task_id):
        resources = self.storage.cache.remove(task_id)
        if not resources:
            return

        for resource in resources:
            self.client.cancel(resource.hash)

    def _add_task(self, files, task_id, resource_hash=None):
        prefix = self.storage.cache.get_prefix(task_id)
        resources = self.storage.get_resources(task_id)

        if prefix and resources:
            logger.warning("Resource manager: Task {} already exists"
                           .format(task_id))
            resource = resources[0]
            return resource.files, resource.hash

        if not files:
            raise RuntimeError("Empty input task resources")
        elif len(files) == 1:
            prefix = os.path.dirname(next(iter(files)))
        else:
            prefix = common_dir(files)

        self.storage.cache.set_prefix(task_id, prefix)
        return self.add_files(files, task_id, resource_hash=resource_hash)

    @staticmethod
    def _add_task_error(error):
        logger.error("Error adding task: %r", error)

    def add_file(self, path, task_id):

        if not path:
            logger.warning("Resource manager: trying to add an empty file "
                           "path for task '%s'", task_id)
            return None, None

        files = {path: os.path.basename(path)}
        return self._add_files(files, task_id)

    def add_files(self, files, task_id, resource_hash=None):

        if not files:
            logger.warning("Resource manager: trying to add an empty file "
                           "collection for task '%s'", task_id)
        elif not all(os.path.isabs(f) for f in files):
            logger.error("Resource manager: trying to add relative file paths "
                         "for task '%s'", task_id)
        else:
            files = {path: self.storage.relative_path(path, task_id)
                     for path in files}
            return self._add_files(files, task_id, resource_hash)

        return None, None

    def _add_files(self, files, task_id, resource_hash=None):

        checked = {f: os.path.exists(f) for f in files}

        if not all(checked.values()):
            missing = [f for f, exists in files.items() if not exists]
            logger.error("Resource manager: missing files (task: %r):\n%s",
                         task_id, missing)
            return None, None

        if resource_hash:
            method, arg = self.client.restore, resource_hash
        else:
            method, arg = self.client.add, files

        try:
            resource_hash = method(arg)
        except Exception as exc:
            logger.error("Resource manager: Error occurred while adding files"
                         ": %r", exc)
            if not resource_hash:
                return None, None
            raise

        resource_files = list(files.values())
        resource_path = self.storage.get_path('', task_id)
        resource = Resource(resource_hash, task_id=task_id,
                            files=resource_files, path=resource_path)
        self._cache_resource(resource)
        return resource_hash, resource_files

    def _cache_resource(self, resource: Resource) -> None:
        """
        Put the resource in storage cache.
        :param resource: Resource instance
        """
        if os.path.exists(resource.path):
            self.storage.cache.add_resource(resource)
            logger.debug("Resource manager: Resource cached: %r", resource)
        else:
            if os.path.isabs(resource.path):
                raise Exception("Resource manager: File not found {} ({})"
                                .format(resource.path, resource.hash))
            logger.warning("Resource does not exist: %r", resource.path)

    def pull_resource(self, entry, task_id,
                      success, error,
                      client=None, client_options=None, async=True):

        resource_path = self.storage.get_path('', task_id)
        resource = Resource(resource_hash=entry[0], task_id=task_id,
                            files=entry[1], path=resource_path)

        if resource.files and self.storage.exists(resource):
            success(entry, resource.files, task_id)
            return

        def success_wrapper(response, **_):
            logger.debug("Resource manager: %s (%s) downloaded",
                         resource.path, resource.hash)

            self._cache_resource(resource)
            files = self._parse_pull_response(response, task_id)
            success(entry, files, task_id)

        def error_wrapper(exception, **_):
            logger.error("Resource manager: error downloading %s (%s): %s",
                         resource.path, resource.hash, exception)
            error(exception, entry, task_id)

        path = self.storage.get_path(resource.path, task_id)
        local = self.storage.cache.get_by_hash(resource.hash)
        os.makedirs(path, exist_ok=True)

        if local:
            try:
                self.storage.copy(local.path, resource.path, task_id)
                success_wrapper(entry)
            except Exception as exc:
                error_wrapper(exc)
        else:
            self._pull(resource, task_id,
                       success=success_wrapper,
                       error=error_wrapper,
                       client=client,
                       client_options=client_options,
                       async=async)

    def _pull(self, resource: Resource, task_id: str,
              success, error,
              client=None, client_options=None, async=True):

        client = client or self.client
        kwargs = dict(
            content_hash=resource.hash,
            filename=self.storage.relative_path(resource.path, task_id),
            filepath=self.storage.get_dir(task_id),
            client_options=client_options
        )

        if async:
            request = AsyncRequest(self._retry, client.get, **kwargs)
            async_run(request, success, error)
        else:
            try:
                success(self._retry(client.get, **kwargs))
            except Exception as e:
                error(e)

    def _parse_pull_response(self, response: list, task_id: str) -> list:
        # response -> [(path, hash, [file_1, file_2, ...])]
        relative = self.storage.relative_path
        if response and len(response[0]) >= 3:
            return [relative(f, task_id) for f in response[0][2]]
        return []


class DummyResourceManager(HyperdriveResourceManager):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = DummyClient()

    def build_client_options(self, **kwargs):
        return DummyClient.build_options(**kwargs)
