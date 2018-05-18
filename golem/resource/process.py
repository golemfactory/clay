import os

from multiprocessing import Pipe
from typing import Optional, List, Dict

from golem.core.ipc import ProcessService
from golem.resource.base.resourcesmanager import ResourceManagerProxyServer, \
    ResourceManagerProxyClient, ResourceManagerOptions


class _ResourceManagerEntry:  # pylint: disable=too-few-public-methods

    __slots__ = ('from_client_conn', 'to_server_conn',
                 'from_server_conn', 'to_client_conn',
                 'resource_manager_options')

    def __init__(self,
                 resource_manager_options: ResourceManagerOptions) -> None:

        self.resource_manager_options = resource_manager_options
        self.from_client_conn, self.to_server_conn = Pipe(duplex=False)
        self.from_server_conn, self.to_client_conn = Pipe(duplex=False)


class _Process(ProcessService):

    def __init__(self, data_dir: str, *resource_manager_options) -> None:
        super().__init__(data_dir)

        self._process = None
        self._servers: Dict[str, ResourceManagerProxyServer] = dict()
        self._entries = {
            options.key: _ResourceManagerEntry(options)
            for options in resource_manager_options
        }

    def server(self, key: str) -> ResourceManagerProxyServer:

        server = self._servers.get(key)
        if server:
            return server

        entry = self._entries[key]
        server = ResourceManagerProxyServer(
            entry.from_client_conn,
            entry.to_client_conn,
            entry.resource_manager_options.data_dir,
            entry.resource_manager_options.dir_manager_method_name
        )
        self._servers[key] = server

        server.start()
        return server

    def _get_spawn_arguments(self) -> List:
        return [
            (entry.resource_manager_options,
             entry.from_server_conn,
             entry.to_server_conn) for entry in self._entries.values()
        ]

    @classmethod
    def _spawn(cls, data_dir: str, *multiple) -> None:

        from golem.core.common import install_reactor, config_logging

        reactor = install_reactor()
        config_logging(suffix='resources', datadir=data_dir)

        from golem.resource.base.resourcesmanager import \
            ResourceManagerBuilder

        for current in multiple:
            options, read_conn, write_conn = current

            builder = ResourceManagerBuilder(options)
            resource_manager = builder.build_resource_manager()
            proxy = ResourceManagerProxyClient(
                read_conn,
                write_conn,
                resource_manager,
            )

            proxy.start()
            reactor.addSystemEventTrigger('before', 'shutdown', proxy.stop)

        reactor.run()


_instance = None


def start_resource_process(data_dir) -> _Process:
    global _instance  # pylint: disable=global-statement

    if not _instance:
        _instance = _Process(
            data_dir,
            ResourceManagerOptions(
                key='golem.client',
                data_dir=os.path.join(data_dir, 'ComputerRes'),
                dir_manager_method_name='get_task_resource_dir'
            ),
            ResourceManagerOptions(
                key='golem.task.taskmanager',
                data_dir=data_dir,
                dir_manager_method_name='get_task_temporary_dir'
            ),
        )
        _instance.start()
    return _instance


def stop_resource_process() -> None:
    if _instance:
        _instance.stop()


def get_resource_manager_proxy(key: str) -> \
        Optional[ResourceManagerProxyServer]:
    if not _instance:
        return None
    return _instance.server(key)
