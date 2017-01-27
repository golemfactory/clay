from golem.network.hyperdrive.client import HyperdriveClient
from golem.resource.base.resourcesmanager import AbstractResourceManager
from golem.resource.client import ClientHandler, ClientConfig, ClientCommands


class HyperdriveResourceManager(ClientHandler, AbstractResourceManager):

    def __init__(self, dir_manager, config=None, resource_dir_method=None):
        ClientHandler.__init__(self, ClientCommands, config or ClientConfig())
        AbstractResourceManager.__init__(self, dir_manager, resource_dir_method)

    def new_client(self):
        return HyperdriveClient(**self.config.client)

    def build_client_options(self, node_id, **kwargs):
        return HyperdriveClient.build_options(node_id, **kwargs)
