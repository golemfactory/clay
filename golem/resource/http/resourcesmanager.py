import os
import random

from golem.resource.base.resourcesmanager import AbstractResourceManager
from golem.resource.client import ClientHandler, IClient, ClientCommands, ClientConfig, ClientOptions, file_multihash
from golem.resource.http.filerequest import UploadFileRequest, DownloadFileRequest

SERVERS = [
    'http://94.23.17.170:8888'
]


class HTTPResourceManagerClient(IClient):

    CLIENT_ID = 'http'
    VERSION = 1.0

    OPTION_SERVER = 'server'

    def __init__(self,
                 host=None,
                 port=None,
                 base=None,

                 default_enc='json',
                 **defaults):

        self.host = host
        self.port = port
        self.base = base
        self.default_enc = default_enc
        self.defaults = defaults

    @classmethod
    def build_options(cls, node_id, **kwargs):
        c = 0
        for i in node_id:
            c += ord(i)

        options = dict()
        options[cls.OPTION_SERVER] = SERVERS[c % len(SERVERS)]

        return ClientOptions(cls.CLIENT_ID, cls.VERSION, options)

    def add(self, files, **kwargs):
        results = []

        if files:
            if isinstance(files, basestring):
                f = files
                if os.path.isfile(f):
                    multihash = file_multihash(f)
                    self._upload(f, multihash, **kwargs)
                    results.append({
                        u'Name': f,
                        u'Hash': multihash
                    })
            else:
                for f in files:
                    results.extend(self.add(f, **kwargs))

        return results

    def get_file(self, multihash, **kwargs):

        file_path = kwargs.pop('filepath')
        file_name = kwargs.pop('filename')
        dst_path = os.path.join(file_path, file_name)
        self._download(multihash, dst_path, **kwargs)

        return dict(Name=file_name, Hash=multihash)

    def id(self, *args, **kwargs):
        return None

    def _download(self, multihash, dst_path, **kwargs):
        url = self._server_from_kwargs(kwargs)
        return DownloadFileRequest(multihash, dst_path, **kwargs).run(url)

    def _upload(self, f, multihash, client_options=None, **kwargs):
        url = self._server_from_kwargs(kwargs)
        return UploadFileRequest(f, multihash, **kwargs).run(url)

    def _server_from_kwargs(self, kwargs):
        server = None
        options = ClientOptions.from_kwargs(kwargs)
        if options:
            server = options.get(self.CLIENT_ID, self.VERSION, self.OPTION_SERVER)
        return server or random.choice(SERVERS)


class HTTPResourceManager(ClientHandler, AbstractResourceManager):
    def __init__(self, dir_manager, config=None, resource_dir_method=None):
        ClientHandler.__init__(self, ClientCommands, config or ClientConfig())
        AbstractResourceManager.__init__(self, dir_manager, resource_dir_method)

    def new_client(self):
        return HTTPResourceManagerClient(**self.config.client)

    def build_client_options(self, node_id, **kwargs):
        return HTTPResourceManagerClient.build_options(node_id, **kwargs)
