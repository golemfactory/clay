import json

import requests

from golem.resource.client import IClient, ClientOptions


class HyperdriveClient(IClient):

    CLIENT_ID = 'hyperg'
    VERSION = 1.0

    def __init__(self, port=3292, host='127.0.0.1'):
        super(HyperdriveClient, self).__init__()
        self.host = host
        self.port = port
        self._url = 'http://{}:{}/api'.format(self.host, self.port)
        self._headers = {'content-type': 'application/json'}
        self._id = None

    @classmethod
    def build_options(cls, node_id, **kwargs):
        return ClientOptions(cls.CLIENT_ID, cls.VERSION)

    def id(self, client_options=None, *args, **kwargs):
        response = self._request(dict(
            command='id'
        ))
        return json.loads(response)['id']

    def add(self, files, recursive=False, client_options=None, **kwargs):
        response = self._request(dict(
            command='upload',
            files=files
        ))
        return json.loads(response)['hash']

    def get_file(self, multihash, client_options=None, **kwargs):
        dst_path = kwargs.pop('filepath')

        self._request(dict(
            command='download',
            hash=multihash,
            dest=dst_path
        ))
        # todo: replace with ResourceBundle
        return [(dst_path, multihash)]

    def pin_add(self, file_path, multihash):
        return self._request(dict(
            command='upload',
            files=[file_path],
            hash=multihash
        ))

    def pin_rm(self, multihash):
        return self._request(dict(
            command='cancel',
            hash=multihash
        ))

    def _request(self, data):
        response = requests.post(self._url,
                                 headers=self._headers,
                                 data=json.dumps(data))
        response.raise_for_status()
        return str(response.content)
