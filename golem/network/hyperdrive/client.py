import json

import requests

from golem.resource.client import IClient, ClientOptions


class HyperdriveClient(IClient):

    CLIENT_ID = 'hyperg'
    VERSION = 1.0

    def __init__(self, port=3292, host='127.0.0.1', timeout=None):
        super(HyperdriveClient, self).__init__()
        self.host = host
        self.port = port

        self._id = None
        self._url = 'http://{}:{}/api'.format(self.host, self.port)
        self._headers = {'content-type': 'application/json'}

    @classmethod
    def build_options(cls, node_id, **kwargs):
        return ClientOptions(cls.CLIENT_ID, cls.VERSION)

    def id(self, client_options=None, *args, **kwargs):
        return self._request(command='id')['id']

    def diagnostics(self):
        return self._request(command='diagnostics')

    def add(self, files, client_options=None, **kwargs):
        result = self._request(
            command='upload',
            files=files
        )
        print "ADD:", result

        return result['hash']

    def get(self, multihash, client_options=None, **kwargs):
        dst_path = kwargs.pop('filepath')

        response = self._request(
            command='download',
            hash=multihash,
            dest=dst_path
        )

        return [(dst_path, multihash, response['files'])]

    def pin_add(self, file_path, multihash):
        return self._request(
            command='upload',
            files=[file_path],
            hash=multihash
        )['hash']

    def pin_rm(self, multihash):
        return self._request(
            command='cancel',
            hash=multihash
        )['ok']

    def _request(self, **data):
        response = requests.post(self._url,
                                 headers=self._headers,
                                 data=json.dumps(data))
        response.raise_for_status()
        return json.loads(response.content)
