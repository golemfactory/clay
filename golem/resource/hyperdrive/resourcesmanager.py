import logging
import os

from golem.network.hyperdrive.client import HyperdriveClient
from golem.network.hyperdrive.daemon_manager import HyperdriveDaemonManager
from golem.resource.base.resourcesmanager import AbstractResourceManager, ResourceBundle
from golem.resource.client import ClientHandler, ClientConfig, ClientCommands

logger = logging.getLogger(__name__)


class HyperdriveResourceManager(ClientHandler, AbstractResourceManager):

    def __init__(self, dir_manager, config=None, resource_dir_method=None):
        ClientHandler.__init__(self, ClientCommands, config or ClientConfig())
        AbstractResourceManager.__init__(self, dir_manager, resource_dir_method)

        # self.daemon_manager = HyperdriveDaemonManager(dir_manager.root_path)
        # self.daemon_manager.start()

    def new_client(self):
        return HyperdriveClient(**self.config.client)

    def build_client_options(self, node_id, **kwargs):
        return HyperdriveClient.build_options(node_id, **kwargs)

    def to_wire(self, resources):
        return [[r.hash, r.files_split] for r in resources]

    def from_wire(self, resources):
        return [[r[0], [os.path.join(*x) for x in r[1]]] for r in resources]

    def add_files(self, files, task_id,
                  absolute_path=False, client=None, client_options=None):

        if not files:
            logger.warn("Resource manager: trying to add an empty file collection for task {}"
                        .format(task_id))
            return

        for f in files:
            if not os.path.exists(f):
                logger.error("Resource manager: file '{}' does not exist"
                             .format(f))

        client = client or self.new_client()
        files = {path: self.storage.relative_path(path, task_id)
                 for path in files}

        response = self._handle_retries(client.add,
                                        self.commands.add,
                                        files,
                                        client_options=client_options)
        self._cache_response(files.values(), response, task_id)

    def add_file(self, path, task_id,
                 absolute_path=False, client=None, client_options=None):

        files = {path: os.path.basename(path)}
        self.add_files(files, task_id,
                       absolute_path=absolute_path,
                       client=client,
                       client_options=client_options)

    def _cache_response(self, resources, resource_hash, task_id):
        res = self._wrap_resource((resource_hash, resources), task_id)
        self._cache_resource(res)

    def _wrap_resource(self, resource, task_id=None):
        resource_hash, files = resource
        path = self.storage.get_path('', task_id)
        return ResourceBundle(files, resource_hash,
                              task_id=task_id, path=path)
