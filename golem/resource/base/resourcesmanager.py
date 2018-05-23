import inspect
import logging
from abc import ABCMeta
from multiprocessing.connection import Connection
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union

from golem.ipc.service import IPCClientService, IPCServerService, IPCService, \
    RPCMixin
from golem.resource.client import ClientOptions as ResourceClientOptions
from golem.resource.messages.helpers import FROM_PYTHON_CONVERTERS, \
    TO_PYTHON_CONVERTERS, build_added, build_empty, build_error, \
    build_pull_resource, build_pulled, build_resources, to_py_pulled_entry, \
    to_py_resource, to_py_resource_entry
from golem.resource.messages.ttypes import AddFile, AddFiles, AddTask, Added, \
    Empty, Error, GetResources, Pulled, RemoveTask, Resources, PullResource

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
    def build_client_options(peers=None, **kwargs) -> ResourceClientOptions:
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
    signature = inspect.signature(entry[1])
    parameters = signature.parameters

    args, kwargs = [], []

    for param, props in parameters.items():
        if param == 'self':
            continue
        elif props.default:
            args.append(param)
        else:
            kwargs.append(param)

    return entry[0], (args, kwargs)


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

    def build(self) -> IResourceManager:
        from golem.resource.hyperdrive.resourcesmanager import \
            HyperdriveResourceManager

        dir_manager = self.build_dir_manager()
        method_name = self.options.dir_manager_method_name
        method = getattr(dir_manager, method_name)

        return HyperdriveResourceManager(
            dir_manager,
            resource_dir_method=method,
        )


class _ProxyMixin(RPCMixin, metaclass=ABCMeta):

    MSG_NAMES: Dict[str, Union[Type, Callable]] = IPCService.build_message_map(
        'golem.resource.messages.ttypes'
    )

    REQ_MSG_BUILDERS: Dict[str, Union[Type, Callable]] = {
        'add_file': AddFile,
        'add_files': AddFiles,
        'add_task': AddTask,
        'remove_task': RemoveTask,
        'get_resources': GetResources,
        'pull_resource': build_pull_resource,
    }

    TO_PY: Dict[Type, Callable] = TO_PYTHON_CONVERTERS
    FROM_PY: Dict[Type, Callable] = FROM_PYTHON_CONVERTERS

    @property
    def reactor(self):
        if not getattr(self, '_reactor', None):
            from twisted.internet import reactor
            setattr(self, '_reactor', reactor)
        return getattr(self, '_reactor')

    def on_error(self, error: Optional[Exception] = None) -> None:
        super().on_error(error)  # noqa pylint: disable=no-member
        logger.error('IPC error: %r', error)

    def on_close(self, error: Optional[Exception] = None) -> None:
        super().on_close(error)  # noqa pylint: disable=no-member
        logger.warning('IPC connection closed: %r', error)


class ResourceManagerProxyClient(_ProxyMixin, IPCClientService,  # noqa # pylint: disable=too-many-ancestors
                                 IResourceManager):

    def __init__(self,
                 read_conn: Connection,
                 write_conn: Connection,
                 data_dir: str,
                 method_name: str = 'get_task_resource_dir') -> None:

        IPCClientService.__init__(self, read_conn, write_conn)

        from golem.resource.dirmanager import DirManager
        from golem.resource.hyperdrive.resource import ResourceStorage

        dir_manager = DirManager(data_dir)
        method = getattr(dir_manager, method_name)

        self.storage = ResourceStorage(dir_manager, method)

    def on_message(self, request_id: bytes, msg: object) -> None:

        if isinstance(msg, Empty):
            return self.on_response(request_id, None)

        elif isinstance(msg, Added):
            resource_entry = to_py_resource_entry(msg.entry)
            return self.on_response(request_id, resource_entry)

        elif isinstance(msg, Pulled):
            pulled_entry = to_py_pulled_entry(msg.entry)
            return self.on_response(request_id, pulled_entry)

        elif isinstance(msg, Resources):
            resources = list(map(to_py_resource, msg.resources))
            return self.on_response(request_id, resources)

        elif isinstance(msg, Error):
            return self.on_response(request_id, Exception(msg.message))

        msg_cls = msg.__class__.__name__
        err = build_error("Unknown msg {}".format(msg_cls))
        self._write(err, request_id=self._new_request_id())

    def _get_method_spec(self, method_name: str) -> Tuple[Optional[List[str]],
                                                          Optional[List[str]]]:
        return _RESOURCE_MANAGER_METHOD_SPECS[method_name]


class ResourceManagerProxyServer(_ProxyMixin, IPCServerService):

    METHOD_MAP: Dict[Type, str] = {
        AddFile: 'add_file',
        AddFiles: 'add_files',
        AddTask: 'add_task',
        RemoveTask: 'remove_task',
        GetResources: 'get_resources',
        PullResource: 'pull_resource',
    }

    RES_MSG_BUILDERS: Dict[str, Callable] = {
        'add_file': build_added,
        'add_files': build_added,
        'add_task': build_added,
        'remove_task': build_empty,
        'get_resources': build_resources,
        'pull_resource': build_pulled
    }

    def _build_error_msg(self,
                         _fn_name: str,
                         result: Any) -> object:

        return build_error(str(result))

    def on_message(self, request_id: bytes, msg: object) -> None:

        if isinstance(msg, Error):
            return logger.error("Unexpected error message received: %r", msg)

        try:
            self.on_request(request_id, msg)
        except Exception as exc:  # pylint: disable=broad-except
            error = build_error(str(exc))
            self._write(error, request_id=self._new_request_id())

    def _execute(self, fn: Callable) -> Any:
        self.reactor.callFromThread(fn)
