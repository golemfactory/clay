import collections
import json
import logging

import requests
from copy import deepcopy
from ipaddress import AddressValueError, ip_address

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

        if client_options:
            filtered_options = client_options.filtered(self.CLIENT_ID,
                                                       self.VERSION)
            if filtered_options:
                peers = filtered_options.options.get('peers')

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
        response.raise_for_status()

        if response.content:
            return json.loads(response.content.decode('utf-8'))


class HyperdriveClientOptions(ClientOptions):

    max_peers = 64

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
            opts.options['peers'] = self.filter_peers(opts.options['peers'],
                                                      excluded_ips)
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

                # FIXME: filter out only private IPs we're not connected to
                # if ip.is_private:
                #     raise ValueError('address {} is private'
                #                      .format(ip))
                if excluded_ips and entry[0] in excluded_ips:
                    raise ValueError('address {} was excluded'
                                     .format(ip))
                if not 0 < port < 65536:
                    raise ValueError('port {} is invalid'
                                     .format(port))
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
