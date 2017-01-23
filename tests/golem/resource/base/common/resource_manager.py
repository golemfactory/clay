import uuid

from golem.resource.base.resourcesmanager import AbstractResourceManager
from golem.resource.client import ClientHandler, ClientCommands, ClientOptions


class MockResourceManager(AbstractResourceManager, ClientHandler):

    class MockClient(object):
        @staticmethod
        def add(resource_path, **_):
            return dict(
                Name=resource_path,
                Hash=str(uuid.uuid4())
            )

    def __init__(self, dir_manager, resource_dir_method=None):
        AbstractResourceManager.__init__(self, dir_manager, resource_dir_method)
        ClientHandler.__init__(self, ClientCommands, {})

    def build_client_options(self, node_id, **kwargs):
        return ClientOptions('mock', 1)

    def new_client(self):
        return self.MockClient()