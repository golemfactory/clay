import inspect
import logging
from abc import ABCMeta
from multiprocessing.connection import Connection
from typing import Optional, Any, Callable

from golem.core.ipc import IPCService, IPCServerService, IPCClientService
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

    def pull_resource(self, entry, task_id, client_options=None, async_=True):
        pass


RESOURCE_MANAGER_METHODS = {
    method_name for method_name, _ in
    inspect.getmembers(IResourceManager, predicate=inspect.isfunction)
}


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

    def _loop(self):
        self.receive()

    def _on_error(self, error: Optional[Exception] = None) -> None:
        super()._on_error(error)
        logger.error('IPC error: %r', error)

    def _on_close(self, error: Optional[Exception] = None) -> None:
        super()._on_close(error)
        logger.warning('IPC connection closed: %r', error)


class ResourceManagerProxyServer(IPCServerService, IResourceManager,  # noqa # pylint: disable=too-many-ancestors
                                 _ResourceManagerProxy):

    METHODS = RESOURCE_MANAGER_METHODS

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


class ResourceManagerProxyClient(IPCClientService, _ResourceManagerProxy):

    def _execute(self, fn: Callable) -> Any:
        self.reactor.callFromThread(fn)
