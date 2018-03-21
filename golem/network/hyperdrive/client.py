import json
import logging
from ipaddress import AddressValueError, ip_address
from typing import Optional

import collections

import math
import requests
from requests import HTTPError
from twisted.internet.defer import Deferred

from golem_messages.helpers import maximum_download_time

from golem.core.async import AsyncHTTPRequest
from golem.resource.client import IClient, ClientOptions

log = logging.getLogger(__name__)


DEFAULT_HYPERDRIVE_PORT = 3282
DEFAULT_HYPERDRIVE_RPC_PORT = 3292
DEFAULT_UPLOAD_RATE = int(384 / 8)  # kBps = kbps / 8


class HyperdriveClient(IClient):

    CLIENT_ID = 'hyperg'
    VERSION = 1.1

    def __init__(self, port=DEFAULT_HYPERDRIVE_RPC_PORT,
                 host='localhost', timeout=None):
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

    def id(self, client_options=None, *args, **kwargs):
        return self._request(command='id')

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

    def restore(self, content_hash, **kwargs):
        response = self._request(
            command='upload',
            id=kwargs.get('id'),
            hash=content_hash
        )
        return response['hash']

    def get(self, content_hash, client_options=None, **kwargs):
        path = kwargs['filepath']
        params = self._download_params(content_hash, client_options, **kwargs)
        response = self._request(**params)
        return [(path, content_hash, response['files'])]

    @classmethod
    def _download_params(cls, content_hash, client_options, **kwargs):
        path = kwargs['filepath']
        peers, size, timeout = None, None, None

        if client_options:
            size = client_options.get(cls.CLIENT_ID, cls.VERSION, 'size')
            timeout = maximum_download_time(size).seconds if size else None

            filtered = client_options.filtered(cls.CLIENT_ID, cls.VERSION)
            if filtered:
                peers = filtered.options.get('peers')

        return dict(
            command='download',
            hash=content_hash,
            dest=path,
            peers=peers or [],
            size=size,
            timeout=timeout
        )

    def cancel(self, content_hash):
        response = self._request(
            command='cancel',
            hash=content_hash
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


class HyperdriveAsyncClient(HyperdriveClient):

    def __init__(self, port=DEFAULT_HYPERDRIVE_RPC_PORT, host='localhost',
                 timeout=None):
        from twisted.web.http_headers import Headers  # imports reactor

        super().__init__(port, host, timeout)

        # default POST request headers
        self._url_bytes = self._url.encode('utf-8')
        self._headers_obj = Headers({'Content-Type': ['application/json']})

    def add_async(self, files, **kwargs):
        params = dict(
            command='upload',
            id=kwargs.get('id'),
            files=files
        )

        return self._async_request(
            params,
            lambda response: response['hash']
        )

    def restore_async(self, content_hash, **kwargs):
        params = dict(
            command='upload',
            id=kwargs.get('id'),
            hash=content_hash
        )

        return self._async_request(
            params,
            lambda response: response['hash']
        )

    def get_async(self, content_hash, client_options=None, **kwargs):
        params = self._download_params(content_hash, client_options, **kwargs)
        path = kwargs['filepath']

        return self._async_request(
            params,
            lambda response: [(path, content_hash, response['files'])]
        )

    def cancel_async(self, content_hash):
        params = dict(
            command='cancel',
            hash=content_hash
        )

        return self._async_request(
            params,
            lambda response: response['hash']
        )

    def _async_request(self, params, response_parser):
        from twisted.web.client import readBody  # imports reactor

        serialized_params = json.dumps(params)
        encoded_params = serialized_params.encode('utf-8')
        _result = Deferred()

        def on_response(response):
            _body = readBody(response)
            _body.addErrback(on_error)

            if response.code == 200:
                _body.addCallback(on_success)
            else:
                _body.addCallback(on_error)

        def on_success(body):
            try:
                decoded = body.decode('utf-8')
                deserialized = json.loads(decoded)
                parsed = response_parser(deserialized)
            except Exception as exc:  # pylint: disable=broad-except
                _result.errback(exc)
            else:
                _result.callback(parsed)

        def on_error(body):
            try:
                decoded = body.decode('utf-8')
            except Exception as exc:  # pylint: disable=broad-except
                _result.errback(exc)
            else:
                _result.errback(HTTPError(decoded))

        deferred = AsyncHTTPRequest.run(
            b'POST',
            self._url_bytes,
            self._headers_obj,
            encoded_params
        )
        deferred.addCallbacks(on_response, _result.errback)

        return _result


class HyperdriveClientOptions(ClientOptions):

    max_peers = 64

    @classmethod
    def replace_host(cls,
                     options: 'HyperdriveClientOptions',
                     address: str) -> Optional['HyperdriveClientOptions']:
        """
        Replaces first peer's address and prepends it to the peers list.
        Filters the options instance but does not remove valid peer addresses.

        :param options: received client options
        :param address: IP address to replace with
        """
        if not (options and options.peers):
            return None

        filtered = options.filtered()
        # Version / client mismatch or no address
        if not (filtered and address):
            return None

        peer = cls.filter_peer(options.peers[0], forced_ip=address)

        if not peer:
            pass
        elif not filtered.peers:
            filtered.peers = [peer]
        elif peer not in filtered.peers:
            filtered.peers.insert(0, peer)
        return filtered

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
                port = int(entry[1])

                if not 0 < port < 65536:
                    raise ValueError('port {} is invalid'.format(port))

                if not forced_ip:
                    cls.verify_ip(ip_str, excluded_ips)
                elif ip_str != forced_ip:
                    log.warning("Replacing provider's IP address %s with %s",
                                ip_str, forced_ip)
                    ip_str = forced_ip

            except (ValueError, TypeError, AddressValueError) as err:
                log.warning('Resource client: %s %s', err, peer)
            else:
                new_entry[protocol] = (ip_str, port)

        if new_entry:
            return new_entry

    @staticmethod
    def verify_ip(ip_str, excluded_ips=None):
        ip = ip_address(ip_str)

        if ip.is_private or ip.is_multicast or ip.is_unspecified:
            raise ValueError('address {} is not allowed'.format(ip))
        if excluded_ips and ip_str in excluded_ips:
            raise ValueError('address {} was excluded'.format(ip))
