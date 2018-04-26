import functools
import inspect
import logging
import uuid
from abc import abstractmethod
from types import FunctionType
from typing import Any, Tuple, Optional, Dict

from twisted.internet.defer import Deferred
from twisted.python.failure import Failure

from golem.core.service import ThreadedService
from golem.resource.client import ClientOptions

logger = logging.getLogger(__name__)


POLL_TIMEOUT = 0.5


class IResourceManager:

    @staticmethod
    def to_wire(resources):
        pass

    @staticmethod
    def from_wire(serialized):
        pass

    @staticmethod
    def build_client_options(peers=None, **kwargs) -> ClientOptions:
        pass

    def add_file(self, path, task_id, async_=False, client_options=None):
        pass

    def add_files(self, files, task_id,  # pylint: disable=too-many-arguments
                  resource_hash=None, async_=False, client_options=None):
        pass

    def add_task(self, files, task_id,  # pylint: disable=too-many-arguments
                 resource_hash=None, async_=True, client_options=None):
        pass

    def remove_task(self, task_id):
        pass

    def get_resources(self, task_id):
        pass

    def pull_resource(self, entry,  # pylint: disable=too-many-arguments
                      task_id, client_options=None, async_=True):
        pass


RESOURCE_MANAGER_METHODS = [
    method_name for method_name, _ in
    inspect.getmembers(IResourceManager, predicate=inspect.isfunction)
]


class ResourceManagerOptions:

    __slots__ = ('_key', '_data_dir', '_dir_manager_method_name')

    def __init__(self, key: str, data_dir: str,
                 dir_manager_method_name: str) -> None:

        self._key = key
        self._data_dir = data_dir
        self._dir_manager_method_name = dir_manager_method_name

    @property
    def key(self) -> str:
        return self._key

    @property
    def data_dir(self) -> str:
        return self._data_dir

    @property
    def dir_manager_method_name(self) -> str:
        return self._dir_manager_method_name


class ResourceManagerBuilder:

    def __init__(self, resource_manager_options):
        self.resource_manager_options = resource_manager_options

    def build_dir_manager(self):
        from golem.resource.dirmanager import DirManager
        return DirManager(self.resource_manager_options.data_dir)

    def build_resource_manager(self) -> IResourceManager:
        from golem.resource.hyperdrive.resourcesmanager import \
            HyperdriveResourceManager

        method_name = self.resource_manager_options.dir_manager_method_name
        dir_manager = self.build_dir_manager()
        dir_manager_method = getattr(dir_manager, method_name)

        return HyperdriveResourceManager(
            dir_manager,
            resource_dir_method=dir_manager_method,
        )


class ResourceManagerProxy(ThreadedService):

    def __init__(self, read_conn, write_conn) -> None:
        super().__init__()

        self.read_conn = read_conn
        self.write_conn = write_conn
        self._reactor = None

    @property
    def reactor(self):
        if not self._reactor:
            from twisted.internet import reactor
            self._reactor = reactor
        return self._reactor

    def _loop(self):
        self._receive()

    @abstractmethod
    def _send(self, *args, **kwargs) -> Optional[Deferred]:
        pass

    def _receive(self) -> Tuple[Optional[str], Any]:

        try:
            # 0.5 second probe to not block the thread for too long
            if self.read_conn.poll(POLL_TIMEOUT):
                response, data = self.read_conn.recv()
                return response, data
        except TypeError as exc:
            logger.error('Invalid response: %r', exc)
        except EOFError as exc:
            logger.debug('Inbound queue was closed on the remote end: %r', exc)

        return None, None


class ResourceManagerProxyServer(ResourceManagerProxy, IResourceManager):

    def __init__(self, read_conn, write_conn, data_dir,
                 method_name='get_task_resource_dir') -> None:
        super().__init__(read_conn, write_conn)

        from golem.resource.dirmanager import DirManager
        from golem.resource.hyperdrive.resource import ResourceStorage

        dir_manager = DirManager(data_dir)

        self._requests: Dict[str, Deferred] = dict()
        self._functions: Dict[str, FunctionType] = dict()

        self.storage = ResourceStorage(
            dir_manager,
            getattr(dir_manager, method_name)
        )

    def __getattribute__(self, item):
        if item in RESOURCE_MANAGER_METHODS:
            if item not in self._functions:
                self._functions[item] = functools.partial(self._send, item)
            return self._functions[item]
        return super().__getattribute__(item)

    def _send(self, fn_name, *args, **kwargs):

        request_id = str(uuid.uuid4())
        request = request_id, (fn_name, args, kwargs)

        deferred = Deferred()

        self._requests[request_id] = deferred
        self.write_conn.send(request)

        return deferred

    def _receive(self):

        request_id, payload = super()._receive()
        if not request_id:
            return

        if request_id not in self._requests:
            logger.error('Unknown request id: %r', request_id)
            return

        deferred = self._requests.pop(request_id)

        if isinstance(payload, Deferred):
            payload.chainDeferred(deferred)
            return

        if isinstance(payload, (Exception, Failure)):
            fn = deferred.errback
        else:
            fn = deferred.callback

        fn(payload)


class ResourceManagerProxyClient(ResourceManagerProxy):

    def __init__(self, read_conn, write_conn, resource_manager) -> None:
        super().__init__(read_conn, write_conn)
        self.rcv_conn = read_conn
        self.resource_manager = resource_manager

    def _send(self, request_id, response):

        try:
            payload = request_id, response
            self.write_conn.send(payload)
        except Exception as exc:  # pylint: disable=broad-except
            logger.error('Cannot send a response for %r: %r',
                         request_id, exc)

    def _receive(self):

        request_id, response = super()._receive()
        if not request_id:
            return

        if not isinstance(response, tuple) or len(response) != 3:
            logger.error('Invalid response: %r', response)
            return

        fn_name, args, kwargs = response
        fn = getattr(self.resource_manager, fn_name, None)

        if not (fn and isinstance(args, (list, tuple))):
            logger.error('Invalid function call: %r (%r, %r)',
                         fn_name, args, kwargs)
            return

        def done(result):
            if isinstance(result, Deferred):
                result.addBoth(lambda r: self._send(request_id, r))
            else:
                self._send(request_id, result)

        def call():
            try:
                result = fn(*args, **kwargs)
            except Exception as exc:  # pylint: disable=broad-except
                result = exc
            done(result)

        self.reactor.callFromThread(call)
