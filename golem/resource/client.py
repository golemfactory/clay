import abc
import hashlib
import logging
import os
import shutil
import socket
import types
import uuid
from enum import Enum
from threading import Lock

import base58
import multihash

import requests
import twisted
from requests.packages.urllib3.exceptions import MaxRetryError, TimeoutError, ReadTimeoutError, \
    ConnectTimeoutError, ConnectionError
from twisted.internet import threads

log = logging.getLogger(__name__)


SHA1_BLOCK_SIZE = 64


def file_sha_256(file_path):
    sha = hashlib.sha256()

    with open(file_path, 'rb') as f:
        buf = f.read(SHA1_BLOCK_SIZE)

        while len(buf) > 0:
            sha.update(buf)
            buf = f.read(SHA1_BLOCK_SIZE)

    return sha.hexdigest()


def file_multihash(file_path):
    h = file_sha_256(file_path)
    encoded = multihash.encode(h, multihash.SHA2_256)
    return base58.b58encode(str(encoded))


class IClient(object):

    @classmethod
    def build_options(cls, node_id, **kwargs):
        raise NotImplementedError

    def add(self, files, recursive=False, client_options=None, **kwargs):
        raise NotImplementedError

    def get_file(self, multihash, client_options=None, **kwargs):
        raise NotImplementedError

    def id(self, client_options=None, *args, **kwargs):
        raise NotImplementedError


class IClientHandler(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def new_client(self):
        pass

    @abc.abstractmethod
    def command_failed(self, exc, cmd, obj_id, **kwargs):
        pass

    @abc.abstractmethod
    def _can_retry(self, exc, cmd, obj_id):
        pass

    @abc.abstractmethod
    def _clear_retry(self, cmd, obj_id):
        pass

    @abc.abstractmethod
    def _handle_retries(self, method, cmd, *args, **kwargs):
        pass

    @staticmethod
    @abc.abstractmethod
    def _async_call(method, success, error, *args, **kwargs):
        pass

    @staticmethod
    @abc.abstractmethod
    def _exception_type(exc):
        pass


class ClientCommands(Enum):
    add = 0
    get = 1
    id = 2


class ClientError(Exception):
    pass


class ClientConfig(object):
    """
    Initial configuration for classes implementing the IClient interface
    """
    def __init__(self, max_concurrent_downloads=3, max_retries=8, timeout=None):

        self.max_concurrent_downloads = max_concurrent_downloads
        self.max_retries = max_retries
        self.client = dict(
            timeout=timeout or (12000, 12000)
        )


class ClientOptions(object):
    """
    Runtime parameters for classes implementing the IClient interface
    """
    def __init__(self, client_id, version, options=None):
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

    @staticmethod
    def from_kwargs(kwargs):
        return kwargs.get('client_options', kwargs.get('options', None))


class ClientHandler(IClientHandler):

    __metaclass__ = abc.ABCMeta
    __retry_lock = Lock()

    timeout_exceptions = (requests.exceptions.ConnectionError,
                          requests.exceptions.ConnectTimeout,
                          requests.exceptions.ReadTimeout,
                          requests.exceptions.RetryError,
                          requests.exceptions.Timeout,
                          requests.exceptions.HTTPError,
                          requests.exceptions.RequestException,
                          twisted.internet.defer.TimeoutError,
                          twisted.python.failure.Failure,
                          socket.timeout, socket.error,
                          MaxRetryError, TimeoutError, ReadTimeoutError,
                          ConnectTimeoutError, ConnectionError)

    def __init__(self, commands_class, config):
        self.commands = commands_class
        self.command_retries = {c: {} for c in commands_class}
        self.config = config

    def _can_retry(self, exc, cmd, obj_id):
        exc_type = self._exception_type(exc)
        if exc_type in self.timeout_exceptions:
            this_cmd = self.command_retries[cmd]

            with self.__retry_lock:
                if obj_id not in this_cmd:
                    this_cmd[obj_id] = 0

                if this_cmd[obj_id] < self.config.max_retries:
                    this_cmd[obj_id] += 1
                    return True

            this_cmd.pop(obj_id, None)

        return False

    def _clear_retry(self, cmd, obj_id):
        self.command_retries[cmd].pop(obj_id, None)

    def _handle_retries(self, method, cmd, *args, **kwargs):
        default_id = args[0] if args else str(uuid.uuid4())
        obj_id = kwargs.pop('obj_id', default_id)
        raise_exc = kwargs.pop('raise_exc', False)
        result = None

        while not result:
            try:
                result = method(*args, **kwargs)
            except Exception as exc:
                self.command_failed(exc, cmd, obj_id)

                if not self._can_retry(exc, cmd, obj_id):
                    self._clear_retry(cmd, obj_id)
                    if raise_exc:
                        raise exc
                    break
            else:
                self._clear_retry(cmd, obj_id)
                return result

    @staticmethod
    def _async_call(method, success, error, *args, **kwargs):
        call = AsyncRequest(method, *args, **kwargs)
        async_run(call, success, error)

    @staticmethod
    def _exception_type(exc):
        if isinstance(exc, twisted.python.failure.Failure):
            exc = exc.value
        exc_type = type(exc)
        if exc_type is types.InstanceType:
            exc_type = exc.__class__
        return exc_type


class AsyncRequest(object):

    """ Deferred job descriptor """

    def __init__(self, method, *args, **kwargs):
        self.method = method
        self.args = args or []
        self.kwargs = kwargs or {}


def default_errback(failure):
    log.error('Caught async exception:\n%s', failure.getTraceback())


def async_run(deferred_call, success=None, error=None):
    """Execute a deferred job in a separate thread (Twisted)"""
    deferred = threads.deferToThread(deferred_call.method,
                                     *deferred_call.args,
                                     **deferred_call.kwargs)
    if error is None:
        error = default_errback
    if success:
        deferred.addCallback(success)
    deferred.addErrback(error)
    return deferred


class TestClient(IClient):

    _resources = dict()
    _id = "test"

    def add(self, resource_path, **_):
        resource_hash = 'hash_' + str(uuid.uuid4())
        self._resources[resource_hash] = resource_path

        return dict(
            Name=resource_path,
            Hash=resource_hash
        )

    def get_file(self, multihash, client_options=None, filename=None, filepath=None, **_):
        path = self._resources[multihash]
        dst = os.path.join(filepath, filename)

        if not os.path.exists(filepath):
            os.makedirs(filepath)

        if path != dst:
            shutil.copy(path, dst)

        return dict(
            Name=os.path.join(filepath, filename),
            Hash=multihash
        )

    def id(self, client_options=None, *args, **kwargs):
        return self._id

    @classmethod
    def build_options(cls, node_id, **kwargs):
        return ClientOptions(cls._id, 1)
