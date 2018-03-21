import abc
import logging
import os
import socket
import uuid
from copy import deepcopy
from twisted.internet.defer import Deferred
from twisted.python.failure import Failure
from types import MethodType
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class ClientError(Exception):
    pass


class IClient(object):

    @classmethod
    def build_options(cls, **kwargs):
        raise NotImplementedError

    def add(self, files, recursive=False, **kwargs):
        raise NotImplementedError

    def cancel(self, content_hash):
        raise NotImplementedError

    def get(self, content_hash, client_options=None, **kwargs):
        raise NotImplementedError

    def id(self, client_options=None, *args, **kwargs):
        raise NotImplementedError


class ClientConfig(object):
    """
    Initial configuration for classes implementing the IClient interface
    """
    def __init__(self, max_retries=3, timeout=None):

        self.max_retries = max_retries
        self.client = dict(
            timeout=timeout or (12000, 12000)
        )


class ClientOptions(object):
    """
    Runtime parameters for classes implementing the IClient interface
    """
    def __init__(self, client_id, version, options=None):
        assert isinstance(client_id, str), 'Client id must be a string'
        assert isinstance(version, float), 'Version must be a fp number'

        self.client_id = client_id
        self.version = version
        self.options = options

    def get(self, client_id, version, option):
        if self.client_id != client_id:
            raise ClientError("Invalid client_id '{}' (expected: '{}')"
                              .format(client_id, self.client_id))
        if self.version != version:
            raise ClientError("Invalid client version '{}' (expected: '{}')"
                              .format(version, self.version))
        return self.options.get(option, None)

    def set(self, **options):
        if not self.options:
            self.options = {}
        self.options.update(options)

    def filtered(self, client_id, version, **_kwargs):
        if self.client_id != client_id:
            logger.warning('Resource client: invalid client id: %s',
                           self.client_id)
        elif not isinstance(self.version, float):
            logger.warning('Resource client: invalid version format: %s',
                           self.version)
        else:
            return self.clone()

    @property
    def peers(self) -> list:
        if isinstance(self.options, dict):
            return self.options.get('peers', [])
        return []

    @peers.setter
    def peers(self, value: list) -> None:
        if not isinstance(self.options, dict):
            self.options = dict()
        self.options['peers'] = value

    def clone(self):
        return self.__class__(
            self.client_id,
            self.version,
            options=deepcopy(self.options)
        )

    @staticmethod
    def from_kwargs(kwargs):
        return kwargs.get('client_options', kwargs.get('options', None))


class ClientHandler(metaclass=abc.ABCMeta):

    retry_exceptions = (
        requests.exceptions.Timeout,
        requests.exceptions.RetryError,
        requests.exceptions.ConnectionError,
        socket.timeout,
        socket.error,
        Failure
    )

    def __init__(self, config: Optional[ClientConfig]):
        self.config = config or ClientConfig()

    def _retry(self, method: MethodType,
               *args,
               raise_exc: Optional[bool] = False,
               **kwargs):

        retries = 0
        result = None

        while not result:
            retries += 1

            try:
                result = method(*args, **kwargs)
            except Exception as exc:
                logger.error('Error executing %r (%r, %r): %r',
                             method, args, kwargs, exc)

                if exc.__class__ not in self.retry_exceptions:
                    raise exc
                if retries < self.config.max_retries:
                    continue
                if raise_exc:
                    raise exc

                return None
            return result

    def _retry_async(self, method: MethodType, *args, **kwargs):
        retries = 0
        result = Deferred()

        def _run():
            nonlocal retries
            retries += 1

            deferred = method(*args, **kwargs)
            deferred.addCallbacks(result.callback, _error)
            return deferred

        def _error(exc):
            if isinstance(exc, Failure):
                exc = exc.value

            if exc.__class__ not in self.retry_exceptions:
                result.errback(exc)
            elif retries < self.config.max_retries:
                _run()
            else:
                result.errback(exc)

        _run()
        return result


class DummyClient(IClient):

    _resources = dict()
    _paths = dict()
    _id = "test"

    def add(self, files: dict, **_):
        return self._add(files)

    def add_async(self, files: dict, **_):
        deferred = Deferred()
        deferred.callback(self._add(files))
        return deferred

    def _add(self, files: dict):
        from golem.core.fileshelper import common_dir

        resource_hash = str(uuid.uuid4())
        self._resources[resource_hash] = files
        self._paths[resource_hash] = common_dir(files.keys())
        return resource_hash

    def get(self,
            content_hash: str,
            client_options: Optional[ClientOptions] = None,
            filepath: Optional[str] = None,
            **_) -> tuple:

        from golem.core.fileshelper import copy_file_tree

        resource = self._resources[content_hash]
        path = self._paths[content_hash]
        files = [os.path.join(filepath, f) for f in resource.values()]

        if path != filepath:
            copy_file_tree(path, filepath)

        return content_hash, files

    def id(self,
           client_options: Optional[ClientOptions] = None,
           *args, **kwargs) -> str:

        return self._id

    def cancel(self, content_hash: str):
        return content_hash

    @staticmethod
    def cancel_async(content_hash: str):
        deferred = Deferred()
        deferred.callback(content_hash)
        return deferred

    @classmethod
    def build_options(cls, **kwargs):
        return ClientOptions(cls._id, 1)
