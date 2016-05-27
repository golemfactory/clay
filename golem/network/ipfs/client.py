import copy
import json
import logging
import os
import shutil
import socket
import tarfile
import urllib2
import uuid
from functools import wraps
from threading import Lock
from types import FunctionType

import ipfsApi
import requests
import twisted
from ipfsApi.commands import ArgCommand
from ipfsApi.http import HTTPClient, pass_defaults
from twisted.internet import threads

from golem.network.transport.tcpnetwork import SocketAddress

logger = logging.getLogger(__name__)

__all__ = [
    'IPFSAddress', 'IPFSCommands', 'IPFSClient',
    'IPFSAsyncCall', 'IPFSAsyncExecutor',
    'StreamFileObject',
    'IPFS_DEFAULT_TCP_PORT',
    'IPFS_DEFAULT_UDP_PORT',
]

IPFS_DEFAULT_TCP_PORT = 4001
IPFS_DEFAULT_UDP_PORT = 4002

BOOTSTRAP_NODES = [
    '/ip4/52.37.205.43/udp/4002/utp/ipfs/QmS8Kx4wTTH7ASvjhqLj12evmHvuqK42LDiHa3tLn24VvB'
]


class StreamFileObject:

    def __init__(self, source):
        self.source = source
        self.source_iter = None

    def read(self, count):
        if not self.source_iter:
            self.source_iter = self.source.iter_content(count)

        try:
            return self.source_iter.next()
        except StopIteration:
            return None


class ChunkedHTTPClient(HTTPClient):

    lock = Lock()
    chunk_size = 1024

    """
    Class implements a workaround for the download method,
    which hangs on reading http response stream data.
    """

    @pass_defaults
    def download(self, path, args, opts=None,
                 filepath=None, filename=None,
                 compress=False, archive=True, **kwargs):
        """
        Downloads a file from IPFS to the directory given by :filepath:
        Support for :filename: was added (which replaces file's hash)
        """
        if opts is None:
            opts = {}
        method = 'get'
        multihash = args[0]

        url = self.base + path
        work_dir = filepath or '.'
        params = [('stream-channels', 'true')]

        if compress:
            params += [('compress', 'true')]
            archive = True
        if archive:
            params += [('archive', 'true')]

        for opt in opts.items():
            params.append(opt)
        for arg in args:
            params.append(('arg', arg))

        if self._session:
            res = self._session.request(method, url,
                                        params=params, stream=True,
                                        **kwargs)
        else:
            res = requests.request(method, url,
                                   params=params, stream=True,
                                   **kwargs)

        res.raise_for_status()

        if archive:
            stream = StreamFileObject(res)
            mode = 'r|gz' if compress else 'r|'
            with tarfile.open(fileobj=stream, mode=mode) as tar_file:
                return self._tar_extract(tar_file, work_dir,
                                         filename, multihash)
        else:
            return self._write_file(res, work_dir, filename, multihash)

    @classmethod
    def _tar_extract(cls, tar_file, work_dir, filename, multihash):

        dst_path = os.path.join(work_dir, filename)
        tmp_dir = os.path.join(work_dir, str(uuid.uuid4()))
        tmp_path = os.path.join(tmp_dir, multihash)

        if not os.path.exists(tmp_dir):
            os.makedirs(tmp_dir)

        with cls.lock:
            if os.path.exists(dst_path):
                os.remove(dst_path)

        tar_file.extractall(tmp_dir)

        if os.path.exists(tmp_path):
            with cls.lock:
                shutil.move(tmp_path, dst_path)

            shutil.rmtree(tmp_dir, ignore_errors=True)
            cls.__log_downloaded(filename, multihash, dst_path)
            return filename, multihash

        return None, None

    @classmethod
    def _write_file(cls, res, work_dir, filename, multihash):
        dst_path = os.path.join(work_dir, filename)
        with open(dst_path, 'wb') as f:
            for chunk in res.iter_content(cls.chunk_size, False):
                if chunk:
                    f.write(chunk)

        cls.__log_downloaded(filename, multihash, dst_path)
        return filename, multihash

    @classmethod
    def __log_downloaded(cls, filename, multihash, dst_path):
        logger.debug("IPFS: downloaded {} ({}) to {}"
                     .format(filename, multihash, dst_path))


def parse_response(resp):

    """ Returns python objects from a string """
    result = []

    if resp:
        if isinstance(resp, basestring):
            parsed = parse_response_entry(resp)
            if parsed:
                result.append(parsed)
        elif isinstance(resp, list):
            for sub_resp in resp:
                if sub_resp:
                    result.extend(parse_response(sub_resp))
        else:
            result.append(resp)

    return result


def parse_response_entry(entry):
    parts = entry.split('\n')
    result = []

    for part in parts:
        if part:
            try:
                result.append(json.loads(part))
            except ValueError:
                result.append(part)

    return result


def response_wrapper(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        return parse_response(func(*args, **kwargs))
    return wrapped


class IPFSCommands(object):
    id = 0
    pin = 1
    unpin = 2
    add = 3
    pull = 4
    bootstrap_add = 5
    bootstrap_rm = 6
    bootstrap_list = 7


class IPFSClientMetaClass(type):

    """ IPFS api client methods decorated with response wrappers """

    def __new__(mcs, class_name, bases, class_dict):
        new_dict = {}
        all_items = copy.copy(class_dict.items())

        for base in bases:
            all_items.extend(copy.copy(base.__dict__.items()))

        for name, attribute in all_items:
            if name in class_dict:
                attribute = class_dict.get(name)
            if type(attribute) == FunctionType and not name.startswith('_'):
                attribute = response_wrapper(attribute)
            new_dict[name] = attribute

        instance = type.__new__(mcs, class_name, bases, new_dict)
        instance._clientfactory = ChunkedHTTPClient

        return instance


class IPFSClient(ipfsApi.Client):

    """ Class of ipfsApi.Client methods decorated with response wrapper """

    __metaclass__ = IPFSClientMetaClass
    _clientfactory = ChunkedHTTPClient

    def __init__(self,
                 host=None,
                 port=None,
                 base=None,
                 default_enc='json',
                 **defaults):

        super(IPFSClient, self).__init__(host=host, port=port,
                                         base=base, default_enc=default_enc,
                                         **defaults)

        self._refs_local = ArgCommand('/refs/local')
        self._bootstrap_list = ArgCommand('/bootstrap/list')

    def refs_local(self, **kwargs):
        return self._refs_local.request(self._client, **kwargs)

    def bootstrap_list(self, **kwargs):
        return self._bootstrap_list.request(self._client, **kwargs)

    def get_file(self, multihash, **kwargs):
        return self._get.request(self._client, multihash, **kwargs)

    def get(self, multihash, **kwargs):
        raise NotImplementedError("Please use the get_file method")


class IPFSConfig:
    def __init__(self, max_concurrent_downloads=4, max_retries=16,
                 client_timeout=None, bootstrap_nodes=None):

        self.max_retries = max_retries
        self.max_concurrent_downloads = max_concurrent_downloads
        self.bootstrap_nodes = bootstrap_nodes if bootstrap_nodes else BOOTSTRAP_NODES
        self.client = {
            'timeout': client_timeout or (24000, 24000)
        }


try:
    from requests.packages.urllib3.exceptions import *
    urllib_exceptions = [MaxRetryError, TimeoutError, ReadTimeoutError,
                         ConnectTimeoutError, ConnectionError]
except ImportError:
    urllib_exceptions = [urllib2.URLError]


class IPFSClientHandler(object):

    timeout_exceptions = [requests.exceptions.ConnectionError,
                          requests.exceptions.ConnectTimeout,
                          requests.exceptions.ReadTimeout,
                          requests.exceptions.RetryError,
                          requests.exceptions.Timeout,
                          requests.exceptions.HTTPError,
                          requests.exceptions.StreamConsumedError,
                          requests.exceptions.RequestException,
                          twisted.internet.defer.TimeoutError,
                          socket.timeout] + urllib_exceptions

    def __init__(self, config=None):

        self.command_retries = dict()
        self.commands = dict()
        self.config = config or IPFSConfig()

        for name, val in IPFSCommands.__dict__.iteritems():
            if not name.startswith('_'):
                self.command_retries[val] = {}
                self.commands[val] = name

    def new_ipfs_client(self):
        return IPFSClient(**self.config.client)

    @staticmethod
    def _ipfs_async_call(method, success, error, *args, **kwargs):
        call = IPFSAsyncCall(method, *args, **kwargs)
        IPFSAsyncExecutor.run(call, success, error)

    def _handle_retries(self, method, cmd, *args, **kwargs):
        working = True
        result = None

        if args:
            obj_id = args[0]
        else:
            obj_id = kwargs.pop('obj_id', method)

        while working:
            try:
                result = method(*args, **kwargs)
                working = False
            except Exception as exc:
                if not self._can_retry(exc, cmd, obj_id):
                    self._clear_retry(cmd, obj_id)
                    raise

        self._clear_retry(cmd, obj_id)
        return result

    def _can_retry(self, exc, cmd, obj_id):
        if type(exc) in self.timeout_exceptions:
            this_cmd = self.command_retries[cmd]

            if obj_id not in this_cmd:
                this_cmd[obj_id] = 0

            if this_cmd[obj_id] < self.config.max_retries:
                this_cmd[obj_id] += 1
                return True

            this_cmd.pop(obj_id, None)

        return False

    def _clear_retry(self, cmd, obj_id):
        self.command_retries[cmd].pop(obj_id, None)


class IPFSAsyncCall(object):

    """ Deferred job descriptor """

    def __init__(self, method, *args, **kwargs):
        self.method = method
        self.args = args
        self.kwargs = kwargs if kwargs else {}


class IPFSAsyncExecutor(object):

    """ Execute a deferred job in a separate thread (Twisted) """
    initialized = False

    @classmethod
    def run(cls, deferred_call, success, error):
        if not cls.initialized:
            cls.__initialize()

        deferred = threads.deferToThread(deferred_call.method,
                                         *deferred_call.args,
                                         **deferred_call.kwargs)
        deferred.addCallbacks(success, error)

    @classmethod
    def __initialize(cls):
        cls.initialized = True
        from twisted.internet import reactor
        reactor.suggestThreadPoolSize(reactor.getThreadPool().max + 4)


class IPFSAddress(object):

    private_nets_172 = ['172.' + str(s) + '.' for s in range(16, 32)]
    private_nets_172_ip6 = ['::' + a for a in private_nets_172]
    private_ip_prefixes = [
        # local
        '127.0.0.',
        # private nets
        '10.', '::10.'
        '192.168.', '::192.168.',
        'fc00:',
    ] + private_nets_172 + private_nets_172_ip6

    def __init__(self, ip_address, node_id, port=IPFS_DEFAULT_TCP_PORT,
                 proto=None, encap_proto=None):
        """
        Build an IPFS address from arguments
        :param address: Node's IP address
        :param node_id: Node's IPFS id
        :param port: Node's IPFS listening port
        :param proto: Transport protocol
        :param encap_proto: Encapsulated protocol, f.e. uTP (in UDP protocol)
        :return: str: IPFS node address
        """
        self.ip_address = ip_address
        self.node_id = node_id
        self.port = int(port)
        self.proto = proto
        self.encap_proto = encap_proto

    def __str__(self):
        ip4, ip6 = 'ip4', 'ip6'
        proto = self.proto or 'tcp'
        port = self.port or IPFS_DEFAULT_TCP_PORT
        sa = SocketAddress(self.ip_address, port)

        if self.encap_proto:
            pattern = '/{}/{}/{}/{}/{}/ipfs/{}'
            return pattern.format(ip6 if sa.ipv6 else ip4,
                                  self.ip_address, proto, port,
                                  self.encap_proto, self.node_id)
        else:
            pattern = '/{}/{}/{}/{}/ipfs/{}'
            return pattern.format(ip6 if sa.ipv6 else ip4,
                                  self.ip_address, proto, port,
                                  self.node_id)

    @staticmethod
    def allowed_ip_address(address):
        if not address or address == '::1':
            return False
        for prefix in IPFSAddress.private_ip_prefixes:
            if address.startswith(prefix):
                return False
        return True

    @staticmethod
    def parse(ipfs_address_str):
        """
        Parse an IPFS address string
        :param ipfs_address_str: str: IPFS address string to parse
        :return: IPFSAddress instance
        """
        if not ipfs_address_str:
            raise ValueError('Empty IPFS address')

        split = ipfs_address_str.split('/')
        split_len = len(split)
        encap = split_len == 8

        if split_len < 7 or split_len > 8:
            raise ValueError('Invalid IPFS address')

        # first elem is empty because of the starting slash
        split = split[1:]

        return IPFSAddress(
            ip_address=split[1],
            proto=split[2],
            port=split[3],
            encap_proto=split[4] if encap else None,
            node_id=split[-1]
        )

