import collections
import json
import logging
from ipaddress import AddressValueError, ip_address
from typing import Optional

import requests
from requests import HTTPError

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
    def build_options(cls, peers=None, **kwargs):
        return HyperdriveClientOptions(cls.CLIENT_ID, cls.VERSION,
                                       options=dict(peers=peers))

    def diagnostics(self, *args, **kwargs):
        raise NotImplementedError()

    def id(self, client_options=None, *args, **kwargs):
        response = self._request(command='id')
        return response['id']

    def addresses(self):
        response = self._request(command='addresses')
        addresses = response['addresses']

        for proto, entry in addresses.items():
            addresses[proto] = (entry['address'], entry['port'])

        return addresses

    def add(self, files, client_options=None, **kwargs):
        response = self._request(
            command='upload',
            id=kwargs.get('id'),
            files=files
        )
        return response['hash']

    def restore(self, multihash, **kwargs):
        response = self._request(
            command='upload',
            id=kwargs.get('id'),
            hash=multihash
        )
        return response['hash']

    def get_file(self, multihash, client_options=None, **kwargs):
        filepath = kwargs.pop('filepath')
        peers = None

        if client_options and isinstance(client_options.options, dict):
            peers = client_options.options.get('peers')

        response = self._request(
            command='download',
            hash=multihash,
            dest=filepath,
            peers=peers
        )
        return [(filepath, multihash, response['files'])]

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

        try:
            response.raise_for_status()
        except HTTPError:
            if response.text:
                raise HTTPError('Hyperdrive HTTP {} error: {}'.format(
                    response.status_code, response.text), response=response)
            raise

        if response.content:
            return json.loads(response.content.decode('utf-8'))


class HyperdriveClientOptions(ClientOptions):

    max_peers = 64

    @classmethod
    def replace_host(cls,
                     options: 'HyperdriveClientOptions',
                     address: str) -> Optional['HyperdriveClientOptions']:
        """
        Replaces host (first) peer's address and prepends it to the peers list.
        Filters the options instance but does not remove valid peer addresses.

        :param options: received client options
        :param address: IP address to replace with
        """
        if not (options and options.peers and address):
            return None

        filtered = options.filtered()
        if not filtered:  # Version / client mismatch
            return None
        elif not address:
            return filtered

        peer = cls.filter_peer(options.peers[0], forced_ip=address)
        if filtered.peers:
            if peer not in filtered.peers:
                filtered.peers.insert(0, peer)
        else:
            filtered.peers = [peer]

        return filtered

    @property
    def peers(self) -> list:
        if isinstance(self.options, dict):
            return self.options.get('peers', [])
        return []

    @peers.setter
    def peers(self, value: list) -> None:
        if not isinstance(self.options, dict):
            self.options = dict()
        self.options['peers'] = value

    def filtered(self,
                 client_id=HyperdriveClient.CLIENT_ID,
                 version=HyperdriveClient.VERSION,
                 excluded_ips=None):

        opts = super(HyperdriveClientOptions, self).filtered(client_id, version)

        if not opts:
            pass

        elif opts.version < 1.0:
            log.warning('Resource client: incompatible version: %s',
                        opts.version)

        elif not isinstance(opts.options, dict):
            log.warning('Resource client: invalid type: %s; dict expected',
                        type(opts.options))

        elif not isinstance(opts.options.get('peers'),
                            collections.Iterable):
            log.warning('Resource client: peers not provided')

        else:
            opts.peers = self.filter_peers(opts.peers, excluded_ips)
            return opts

    @classmethod
    def filter_peers(cls, peers, excluded_ips=None):
        result = list()

        for peer in peers:
            entry = cls.filter_peer(peer, excluded_ips)
            if not entry:
                continue

            result.append(entry)
            if len(result) == cls.max_peers:
                break

        return result

    @classmethod
    def filter_peer(cls, peer, excluded_ips=None, forced_ip=None):
        if not isinstance(peer, dict):
            return

        new_entry = dict()

        for protocol, entry in peer.items():
            try:
                ip_str = entry[0]
                ip = ip_address(ip_str)
                port = int(entry[1])

                if ip_str != forced_ip:
                    if ip.is_private or ip.is_multicast or ip.is_unspecified:
                        raise ValueError('address {} is not allowed'.format(ip))
                    if excluded_ips and ip_str in excluded_ips:
                        raise ValueError('address {} was excluded'.format(ip))

                if not 0 < port < 65536:
                    raise ValueError('port {} is invalid'.format(port))

                if forced_ip and ip_str != forced_ip:
                    log.warning("Replacing provider's IP address %s with %s",
                                ip, forced_ip)
                    ip_str = forced_ip

            except (ValueError, TypeError, AddressValueError) as err:
                log.warning('Resource client: %s %s', err, peer)
            else:
                new_entry[protocol] = (ip_str, port)

        if new_entry:
            return new_entry
