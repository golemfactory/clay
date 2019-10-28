import logging

import os
import typing
from collections import Iterable, Sized
from functools import partial
from twisted.internet.defer import Deferred

from golem.core.fileshelper import common_dir
from golem.network.hyperdrive.client import HyperdriveAsyncClient
from golem.resource.client import ClientHandler, DummyClient
from golem.resource.hyperdrive.resource import Resource, ResourceStorage, \
    ResourceError

logger = logging.getLogger(__name__)


def is_collection(obj):
    return isinstance(obj, Iterable) and isinstance(obj, Sized)


def handle_async(on_error, async_param='async_'):
    def decorator(func):
        default = default_argument_value(func, async_param)

        def wrapper(*args, **kwargs):
            if kwargs.get(async_param, default):
                return _handle_async(func, on_error, *args, **kwargs)
            return func(*args, **kwargs)
        return wrapper
    return decorator


def _handle_async(func, on_error, *args, **kwargs):
    deferred = Deferred()
    deferred.addErrback(on_error)

    try:
        result = func(*args, **kwargs)
        if isinstance(result, Deferred):
            result.chainDeferred(deferred)
        else:
            deferred.callback(result)
    except Exception as exc:  # pylint: disable=broad-except
        deferred.errback(exc)
    return deferred


def default_argument_value(func, name):
    """
    Get function's default argument value
    :param func: Function to inspect
    :param name: Argument name
    :return: Default value or None if does not exist
    """
    import inspect
    signature = inspect.signature(func)

    try:
        return next(
            val.default
            for key, val in signature.parameters.items()
            if key == name and val.default is not inspect.Parameter.empty
        )
    except StopIteration:
        return None


def log_error(msg, exc):
    logger.error(msg, exc)
    # If this function is an error handler for a Deferred instance,
    # we need to return the exception for other handlers.
    return exc


class HyperdriveResourceManager(ClientHandler):

    def __init__(  # noqa pylint: disable=too-many-arguments
            self, dir_manager, daemon_address=None, config=None,  # noqa pylint: disable=unused-argument
            resource_dir_method=None,
            client_kwargs: typing.Optional[dict] = None,
    ) -> None:
        super().__init__(config)

        self.client = HyperdriveAsyncClient(  # type: ignore
            **self.config.client, **(client_kwargs or {}))
        logger.info("Initializing %s, using %s",
                    self.__class__.__name__, self.client)

        self.storage = ResourceStorage(dir_manager, resource_dir_method or
                                       dir_manager.get_task_resource_dir)

    @staticmethod
    def build_client_options(peers=None, **kwargs):
        return HyperdriveAsyncClient.build_options(peers=peers, **kwargs)

    @staticmethod
    def to_wire(resources):
        iterator = filter(None, resources)
        return list(resource.serialize() for resource in iterator)

    @staticmethod
    def from_wire(serialized):
        iterator = filter(lambda x: is_collection(x) and len(x) > 1,
                          serialized)
        results = [Resource.deserialize(entry) for entry in iterator
                   if is_collection(entry) and len(entry) > 1]

        if len(results) != len(serialized):
            logger.warning("Errors occurred while deserializing %r", serialized)

        return results

    def get_resources(self, res_id):
        return self.storage.get_resources(res_id)

    def remove_resources(self, res_id):
        resources = self.storage.cache.remove(res_id)
        if not resources:
            raise ResourceError("Resource manager: no resources to remove with "
                                "id '{}'".format(res_id))

        on_error = partial(log_error, "Error removing resources for id: %r")
        for resource in resources:
            self.client.cancel_async(resource.hash) \
                .addErrback(on_error)

    @handle_async(on_error=partial(log_error,
                                   "Error adding resources for id: %r"))
    def add_resources(self, files, res_id,  # pylint: disable=too-many-arguments
                      resource_hash=None, async_=True, client_options=None):

        prefix = self.storage.cache.get_prefix(res_id)
        resources = self.storage.get_resources(res_id)

        if prefix and resources:
            logger.warning("Resource manager: Resources for id '%s' exist",
                           res_id)
            return resources[0].hash, resources[0].files

        if not files:
            raise ResourceError("Empty files for resources for id {}".format(
                res_id))
        if len(files) == 1:
            prefix = os.path.dirname(next(iter(files)))
        else:
            prefix = common_dir(files)

        self.storage.cache.set_prefix(res_id, prefix)
        return self._add_files(files, res_id,
                               resource_hash=resource_hash,
                               client_options=client_options,
                               async_=async_)

    @handle_async(on_error=partial(log_error, "Error adding file: %r"))
    def add_file(self, path, res_id, async_=False, client_options=None):
        return self._add_files([path], res_id, async_=async_,
                               client_options=client_options)

    @handle_async(on_error=partial(log_error, "Error adding files: %r"))
    def add_files(self, files, res_id,  # pylint: disable=too-many-arguments
                  resource_hash=None, async_=False, client_options=None):
        return self._add_files(files, res_id,
                               resource_hash=resource_hash,
                               async_=async_,
                               client_options=client_options)

    def _add_files(self, files, res_id,  # pylint: disable=too-many-arguments
                   resource_hash=None, async_=False, client_options=None):
        """
        Adds files to hyperdrive.
        :param files: File collection
        :param res_id: Resources id
        :param resource_hash: If set, a 'restore' method is called; 'add'
        otherwise
        :param async_: Use asynchronous methods of HyperdriveAsyncClient
        :return: Deferred if async_; (hash, file list) otherwise
        """
        if not all(os.path.isabs(f) for f in files):
            raise ResourceError("Resource manager: trying to add relative file "
                                "paths for resources with id '{}'"
                                ":\n{}".format(res_id, files))

        if len(files) == 1:
            files = {path: os.path.basename(path)
                     for path in files}
        else:
            files = {path: self.storage.relative_path(path, res_id)
                     for path in files}

        missing = [f for f in files if not os.path.exists(f)]
        if missing:
            raise ResourceError("Resource manager: missing files "
                                "(resources id: '{}'):\n{}".format(
                                    res_id, missing))

        if async_:
            return self._add_files_async(resource_hash, files, res_id,
                                         client_options=client_options)
        return self._add_files_sync(resource_hash, files, res_id,
                                    client_options=client_options)

    def _add_files_async(self, resource_hash: str, files: dict, res_id: str,
                         client_options=None):
        """
        Adds files to hyperdrive using the asynchronous HyperdriveAsyncClient
        method.
        :param resource_hash: If set, the 'restore_async' method is called;
        'add_async' otherwise
        :param files: Dictionary of {full_path: relative_path} of files
        :param res_id: Resources id
        :return: Deferred object
        """
        resource_files = list(files.values())
        result = Deferred()

        def success(hyperdrive_hash):
            self._cache_files(hyperdrive_hash, resource_files, res_id)
            result.callback((hyperdrive_hash, resource_files))

        if resource_hash:
            client_result = self.client.restore_async(
                resource_hash, client_options=client_options)
        else:
            client_result = self.client.add_async(
                files, client_options=client_options)

        client_result.addCallbacks(success, result.errback)
        return result

    def _add_files_sync(self, resource_hash: str, files: dict, res_id: str,
                        client_options=None):
        """
        Adds files to hyperdrive using the synchronous HyperdriveClient method.
        :param resource_hash: If set, the 'restore' method is called; 'add'
        otherwise
        :param files: Dictionary of {full_path: relative_path} of files
        :param res_id: Resources id
        :return: hash, file list
        """
        resource_files = list(files.values())

        try:
            if resource_hash:
                self.client.restore(resource_hash,
                                    client_options=client_options)
            else:
                resource_hash = self.client.add(files,
                                                client_options=client_options)
        except Exception as exc:
            raise ResourceError("Resource manager: error adding files: {}"
                                .format(exc))

        self._cache_files(resource_hash, resource_files, res_id)
        return resource_hash, resource_files

    def _cache_files(self, resource_hash: str, files: Iterable, res_id: str):
        """
        Put the files in storage cache.
        :param resource_hash: Hash that files are identified by
        :param files: Collection of files
        :param res_id: Task id that files are associated with
        """
        resource_path = self.storage.get_path('', res_id)
        resource = Resource(resource_hash, res_id=res_id,
                            files=list(files), path=resource_path)
        self._cache_resource(resource)

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
                raise ResourceError("Resource manager: File not found {} ({})"
                                    .format(resource.path, resource.hash))
            logger.warning("Resource does not exist: %r", resource.path)

    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-locals
    def pull_resource(self, entry, res_id,
                      success, error,
                      client=None, client_options=None, async_=True):

        resource_path = self.storage.get_path('', res_id)
        resource = Resource(resource_hash=entry[0], res_id=res_id,
                            files=entry[1], path=resource_path)

        if resource.files and self.storage.exists(resource):
            success(entry, resource.files, res_id)
            return

        def success_wrapper(response, **_):
            logger.debug("Downloaded resource. path=%s, hash=%s",
                         resource.path, resource.hash)

            self._cache_resource(resource)
            files = self._parse_pull_response(response, res_id)
            success(entry, files, res_id)

        def error_wrapper(exception, **_):
            logger.warning("Error downloading resource. res_id=%s",
                           resource.res_id)
            logger.debug("path=%s, hash=%s, error=%s",
                         resource.path, resource.hash, exception)
            error(exception, entry, res_id)

        logger.debug("Preparing to download resource. path=%s, hash=%s",
                     resource.path, resource.hash)
        path = self.storage.get_path(resource.path, res_id)
        local = self.storage.cache.get_by_hash(resource.hash)
        os.makedirs(path, exist_ok=True)

        logger.debug("Pulling resource. local=%r, hash=%s",
                     local, resource.hash)

        if local:
            try:
                self.storage.copy(local.path, resource.path, res_id)
                success_wrapper(entry)
            except Exception as exc:
                error_wrapper(exc)
        else:
            self._pull(resource, res_id,
                       success=success_wrapper,
                       error=error_wrapper,
                       client=client,
                       client_options=client_options,
                       async_=async_)

    # pylint: disable=too-many-arguments
    def _pull(self, resource: Resource, res_id: str,
              success, error,
              client=None, client_options=None, async_=True):

        client = client or self.client
        kwargs = dict(
            content_hash=resource.hash,
            filename=self.storage.relative_path(resource.path, res_id),
            filepath=self.storage.get_dir(res_id),
            client_options=client_options
        )

        logger.debug("Pull config. async=%r, kwargs=%r",
                     async_, kwargs)

        if async_:
            deferred = self._retry_async(client.get_async, **kwargs)
            deferred.addCallbacks(success, error)
        else:
            try:
                success(self._retry(client.get, **kwargs))
            except Exception as e:
                error(e)

    def _parse_pull_response(self, response: list, res_id: str) -> list:
        # response -> [(path, hash, [file_1, file_2, ...])]
        relative = self.storage.relative_path
        if response and len(response[0]) >= 3:
            return [relative(f, res_id) for f in response[0][2]]
        return []


class DummyResourceManager(HyperdriveResourceManager):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = DummyClient()

    def build_client_options(self, **kwargs):
        return DummyClient.build_options(**kwargs)
