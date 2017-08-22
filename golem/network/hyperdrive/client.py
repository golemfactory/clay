import collections
import json
import logging

import ipaddress
import requests

from golem.resource.client import IClient, ClientOptions

log = logging.getLogger(__name__)


class HyperdriveClient(IClient):

    CLIENT_ID = 'hyperg'
    VERSION = 1.1

    def __init__(self, port=3292, host='localhost', timeout=None):
        super(HyperdriveClient, self).__init__()

        # API destination address
        self.host = host
        self.port = port
        # connection / read timeout
        self.timeout = timeout

        # default POST request headers
        self._url = 'http://{}:{}/api'.format(self.host, self.port)
        self._headers = {'content-type': 'application/json'}

    @classmethod
    def build_options(cls, node_id, peers=None, **kwargs):
        return ClientOptions(cls.CLIENT_ID, cls.VERSION,
                             options=dict(peers=peers))

    @classmethod
    def filter_options(cls, client_options):
        opts = super(HyperdriveClient, cls).filter_options(client_options)

        if not opts:
            return None

        elif opts.version < 1.1:
            log.warning('Resource client: incompatible version: %s',
                        type(opts.version))

        elif not isinstance(opts.options, dict):
            log.warning('Resource client: invalid type: %s; dict expected',
                        type(opts.options))

        elif not isinstance(opts.options.get('peers'),
                            collections.Iterable):
            log.warning('Resource client: peers not provided')

        else:
            try:
                opts.options['peers'] = cls._filter_peers(opts.options['peers'])
            except (AttributeError, ValueError) as err:
                log.warning('Resource client: address error: %s', err)
            else:
                return opts

    @classmethod
    def _filter_peers(cls, peers):
        result = list()

        for peer in peers:
            if not peer:
                continue

            new_entry = dict()

            for protocol, entry in peer.items():
                address = ipaddress.ip_address(entry['address'])
                port = int(entry['port'])

                if 0 < port < 65536 and not address.is_private:
                    new_entry[protocol] = entry

            if new_entry:
                result.append(new_entry)

        return result

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

        filepath = kwargs.pop('filepath')
        client_options = self.filter_options(client_options)

        if client_options:
            peers = client_options.options['peers']
        else:
            peers = None

        response = self._request(
            command='download',
            hash=multihash,
            dest=filepath,
            peers=peers
        )
        return [(filepath, multihash, response['files'])]

    def pin_add(self, filepath, multihash):
        response = self._request(
            command='upload',
            files=[filepath],
            hash=multihash
        )
        return response['hash']

    def pin_rm(self, multihash):
        response = self._request(
            command='cancel',
            hash=multihash
        )
        return response['hash']

    def peers(self, multihash, peers):
        self._request(
            comand='peers',
            hash=multihash,
            peers=peers
        )

    def _request(self, **data):
        response = requests.post(url=self._url,
                                 headers=self._headers,
                                 data=json.dumps(data),
                                 timeout=self.timeout)
        response.raise_for_status()

        if response.content:
            return json.loads(response.content.decode('utf-8'))
