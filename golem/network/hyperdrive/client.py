import json

import requests

from golem.resource.client import IClient, ClientOptions


class HyperdriveClient(IClient):

    CLIENT_ID = 'hyperg'
    VERSION = 1.0

    def __init__(self, port=3292, host='127.0.0.1', timeout=None):
        super(HyperdriveClient, self).__init__()

        # destination address
        self.host = host
        self.port = port
        # connection / read timeout
        self.timeout = timeout

        # default POST request headers
        self._url = 'http://{}:{}/api'.format(self.host, self.port)
        self._headers = {'content-type': 'application/json'}

    @classmethod
    def build_options(cls, node_id, **kwargs):
        return ClientOptions(cls.CLIENT_ID, cls.VERSION)

    def diagnostics(self, *args, **kwargs):
        raise NotImplementedError()

    def id(self, client_options=None, *args, **kwargs):
        response = self._request(command='id')
        return response['id']

    def addresses(self):
        response = self._request(command='addresses')
        return response['addresses']

    def add(self, files, client_options=None, **kwargs):
        response = self._request(
            command='upload',
            id=kwargs.get('id'),
            files=files
        )
        return response['hash']

    def get_file(self, multihash, client_options=None, **kwargs):
        dst_path = kwargs.pop('filepath')
        response = self._request(
            command='download',
            hash=multihash,
            dest=dst_path
        )
        return [(dst_path, multihash, response['files'])]

    def pin_add(self, file_path, multihash):
        response = self._request(
            command='upload',
            files=[file_path],
            hash=multihash
        )
        return response['hash']

    def pin_rm(self, multihash):
        response = self._request(
            command='cancel',
            hash=multihash
        )
        return response['hash']

    def _request(self, **data):
        response = requests.post(url=self._url,
                                 headers=self._headers,
                                 data=json.dumps(data),
                                 timeout=self.timeout)
        response.raise_for_status()
        return json.loads(response.content)
