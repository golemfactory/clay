import inspect
import logging
from abc import ABCMeta
from multiprocessing.connection import Connection
from typing import Optional, Any, Callable, Dict, Type, Tuple, List

from golem.ipc.service import IPCService, IPCServerService, IPCClientService
from golem.resource.client import ClientOptions
from golem.resource.messages.ttypes import AddFile, AddFiles, AddTask, \
    RemoveTask, GetResources, PullResource, Error, Response, Resources

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

    def pull_resource(self, entry, task_id, client_options=None, async_=True):
        pass


def _read_args_and_kwargs(entry):
    spec = inspect.getfullargspec(entry[1])

    if spec.args and spec.args[0] == 'self':
        args = spec.args[1:]
    else:
        args = spec.args

    return entry[0], (args, spec.kwonlyargs)


_RESOURCE_MANAGER_METHOD_SPECS = dict(map(
    _read_args_and_kwargs,
    inspect.getmembers(IResourceManager, predicate=inspect.isfunction)
))


class ResourceManagerOptions:  # pylint: disable=too-few-public-methods

    __slots__ = ('key', 'data_dir', 'dir_manager_method_name')

    def __init__(self,
                 key: str,
                 data_dir: str,
                 dir_manager_method_name: str) -> None:

        self.key = key
        self.data_dir = data_dir
        self.dir_manager_method_name = dir_manager_method_name


class ResourceManagerBuilder:

    def __init__(self,
                 resource_manager_options: ResourceManagerOptions) -> None:

        self.options = resource_manager_options

    def build_dir_manager(self):
        from golem.resource.dirmanager import DirManager
        return DirManager(self.options.data_dir)

    def build_resource_manager(self) -> IResourceManager:
        from golem.resource.hyperdrive.resourcesmanager import \
            HyperdriveResourceManager

        dir_manager = self.build_dir_manager()
        method_name = self.options.dir_manager_method_name
        method = getattr(dir_manager, method_name)

        return HyperdriveResourceManager(
            dir_manager,
            resource_dir_method=method,
        )


class _ResourceManagerProxy(IPCService, metaclass=ABCMeta):

    def __init__(self,
                 read_conn: Connection,
                 write_conn: Connection) -> None:

        super().__init__(read_conn, write_conn)
        self._reactor = None

    @property
    def reactor(self):
        if not self._reactor:
            from twisted.internet import reactor
            self._reactor = reactor
        return self._reactor

    def _on_error(self, error: Optional[Exception] = None) -> None:
        super()._on_error(error)
        logger.error('IPC error: %r', error)

    def _on_close(self, error: Optional[Exception] = None) -> None:
        super()._on_close(error)
        logger.warning('IPC connection closed: %r', error)

    def _get_method_spec(self, method_name: str) -> Tuple[Optional[List[str]],
                                                          Optional[List[str]]]:
        return _RESOURCE_MANAGER_METHOD_SPECS[method_name]


class ResourceManagerProxyServer(IPCServerService, IResourceManager,  # noqa # pylint: disable=too-many-ancestors
                                 _ResourceManagerProxy):

    METHOD_MAP: Dict[str, Type] = {
        'add_file': AddFile,
        'add_files': AddFiles,
        'add_task': AddTask,
        'remove_task': RemoveTask,
        'get_resources': GetResources,
        'pull_resource': PullResource
    }

    def __init__(self,
                 read_conn: Connection,
                 write_conn: Connection,
                 data_dir: str,
                 method_name: str = 'get_task_resource_dir') -> None:

        super().__init__(read_conn, write_conn)

        from golem.resource.dirmanager import DirManager
        from golem.resource.hyperdrive.resource import ResourceStorage

        dir_manager = DirManager(data_dir)
        method = getattr(dir_manager, method_name)

        self.storage = ResourceStorage(dir_manager, method)

    def _on_message(self, msg: object) -> None:

        if isinstance(msg, Response):
            return self._on_response(msg.request_id, None)

        elif isinstance(msg, Resources):
            return self._on_response(msg.request_id, msg.resources)

        elif isinstance(msg, Error):
            return self._on_response(msg.request_id, Exception(msg.message))

        else:
            logger.error("Unknown message received: %r", msg)


class ResourceManagerProxyClient(IPCClientService, _ResourceManagerProxy):

    METHOD_MAP: Dict[str, Type] = {
        'add_file': Response,
        'add_files': Response,
        'add_task': Response,
        'remove_task': Response,
        'get_resources': Resources,
        'pull_resource': Response
    }

    def __init__(self,
                 read_conn: Connection,
                 write_conn: Connection,
                 proxy_object: object) -> None:

        super().__init__(read_conn, write_conn, proxy_object)
        self._cls_to_fn = {v: k for k, v in self.METHOD_MAP.items()}

    def _build_error_msg(self,
                         request_id: bytes,
                         fn_name: str,
                         result: Any) -> object:

        return Error(request_id, str(result))

    def _on_message(self, msg: object) -> None:

        if isinstance(msg, Error):
            logger.error("Unexpected error message received: %r", msg)
        else:
            self._on_request(msg)

    def _execute(self, fn: Callable) -> Any:
        self.reactor.callFromThread(fn)
