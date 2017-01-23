from golem.resource.base.resourcesmanager import AbstractResourceManager
from golem.resource.client import ClientHandler, ClientCommands, ClientConfig, ClientOptions
from golem.resource.http.resourcesmanager import HTTPResourceManagerClient
from golem.resource.swift.api import OpenStackSwiftAPIClient, SERVICE_NAME


class OpenStackSwiftClient(HTTPResourceManagerClient):

    CLIENT_ID = 'swift'
    VERSION = 1.0

    OPTION_REGION = 'region'

    API = OpenStackSwiftAPIClient()

    @classmethod
    def build_options(cls, node_id, *args, **kwargs):
        options = dict()
        options[cls.OPTION_REGION] = cls.API.get_region_url_for_node(node_id)
        return ClientOptions(cls.CLIENT_ID, cls.VERSION, options)

    def id(self, *args, **kwargs):
        return SERVICE_NAME

    def delete(self, multihash, **kwargs):
        return self.API.delete(multihash, self._region_from_kwargs(kwargs))

    def _download(self, multihash, dst_path, **kwargs):
        return self.API.get(multihash, dst_path, self._region_from_kwargs(kwargs))

    def _upload(self, f, multihash, **kwargs):
        return self.API.put(f, multihash, self._region_from_kwargs(kwargs))

    def _region_from_kwargs(self, kwargs):
        region = None
        options = ClientOptions.from_kwargs(kwargs)
        if options:
            region = options.get(self.CLIENT_ID, self.VERSION, self.OPTION_REGION)
        return region or self.API.get_region_url_for_node(None)


class OpenStackSwiftResourceManager(ClientHandler, AbstractResourceManager):

    def __init__(self, dir_manager, config=None, resource_dir_method=None):
        ClientHandler.__init__(self, ClientCommands, config or ClientConfig())
        AbstractResourceManager.__init__(self, dir_manager, resource_dir_method)

    def new_client(self):
        return OpenStackSwiftClient(**self.config.client)

    def build_client_options(self, node_id, **kwargs):
        return OpenStackSwiftClient.build_options(node_id, **kwargs)
