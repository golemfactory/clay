import abc
import copy
import jsonpickle as json
import logging
import os
import shutil
import tarfile
import urllib
import uuid
from functools import wraps
from threading import Lock
from types import FunctionType

import ipfsApi
import requests
from ipfsApi.commands import ArgCommand
from ipfsApi.http import HTTPClient, pass_defaults

from golem.core.hostaddress import ip_address_private
from golem.http.stream import StreamMonitor, ChunkStream
from golem.network.transport.tcpnetwork import SocketAddress
from golem.resource.client import ClientCommands, ClientConfig, ClientHandler, IClient, ClientOptions

logger = logging.getLogger(__name__)

IPFS_DEFAULT_TCP_PORT = 4001
IPFS_DEFAULT_UDP_PORT = 4002

IPFS_BOOTSTRAP_NODES = [
    '/ip4/94.23.17.170/tcp/4001/ipfs/QmXR8NZWUJhsbixGmeNoC6DxJQxySCP3BEHRm3mbk8Yv7G',
    '/ip4/52.40.149.71/tcp/4001/ipfs/QmX47BhziLbt3CVYsSmrH5xGfQM1t2T5De2XFZFfR4EBWr',
    '/ip4/52.40.149.24/tcp/4001/ipfs/QmNSjTqoyieCCBPBMGeSzzg3C4SNUDuqg8ob16L83X4WRf'
]


class IPFSCommands(ClientCommands):
    pin = 3
    unpin = 4

    bootstrap_add = 5
    bootstrap_rm = 6
    bootstrap_list = 7

    swarm_connect = 8
    swarm_disconnect = 9
    swarm_peers = 10

IPFSCommands.build_names()


class IPFSConfig(ClientConfig):

    def __init__(self, max_concurrent_downloads=3, max_retries=8,
                 timeout=None, bootstrap_nodes=None):

        super(IPFSConfig, self).__init__(max_concurrent_downloads,
                                         max_retries,
                                         timeout)
        if bootstrap_nodes:
            self.bootstrap_nodes = bootstrap_nodes
        else:
            self.bootstrap_nodes = IPFS_BOOTSTRAP_NODES


class IPFSHTTPClient(HTTPClient):

    lock = Lock()
    chunk_size = 1024

    """
    Class implements a workaround for the download method,
    which hangs on reading http response stream data.
    """

    @pass_defaults
    def download(self, path, args=[], opts={},
                 filepath=None, filename=None,
                 compress=True, archive=True, **kwargs):
        """
        Downloads a file from IPFS to the directory given by :filepath:
        Support for :filename: was added (which replaces file's hash)
        """
        multihash = args[0]

        url = self.base + path
        work_dir = filepath or '.'
        params = [('stream-channels', 'true')]
        mode = 'r|gz' if compress else 'r|'

        if compress:
            params += [('compress', 'true')]
            archive = True
        if archive:
            params += [('archive', 'true')]

        if not (archive and compress):
            raise Exception("Only compress + archive mode is supported")

        for opt in opts.items():
            params.append(opt)
        for arg in args:
            params.append(('arg', arg))

        uri = '/'.join([''] + url.split('/')[3:])
        query_params = '?' + urllib.urlencode(params) if params else ''

        socket_stream = ChunkStream((self.host, self.port),
                                    uri + query_params,
                                    kwargs.pop('timeout', None))
        socket_stream.connect()

        try:
            StreamMonitor.monitor(socket_stream)

            with tarfile.open(fileobj=socket_stream, mode=mode) as tar_file:
                return self._tar_extract(tar_file, work_dir,
                                         filename, multihash)
        finally:
            socket_stream.disconnect()

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


class IPFSClientMetaClass(abc.ABCMeta):

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
        instance._clientfactory = IPFSHTTPClient

        return instance


class IPFSClientFileCommand(ipfsApi.Command):

    def request(self, client, *args, **kwargs):
        return self.post_files(client, args[0], **kwargs)

    def post_files(self, client, f, **kwargs):
        responses = []
        url = client.base + self.path + '?' + urllib.urlencode([
            ('stream-channels', 'true'),
            ('encoding', 'json')
        ])

        if isinstance(f, basestring):
            responses.append(self.post_file(url, f))
        else:
            for file_path in f:
                responses.append(self.post_file(url, file_path))

        return responses

    @staticmethod
    def post_file(url, file_path):
        if os.path.isfile(file_path):
            with open(file_path, 'rb') as input_file:
                file_name = os.path.basename(file_path)
                files = dict(
                    file=(
                        file_name,
                        input_file,
                        'application/octet-stream'
                    )
                )
                r = requests.post(url, files=files)
                return r.text
        return None


class IPFSClient(IClient, ipfsApi.Client):

    """ Class of ipfsApi.Client methods decorated with response wrapper """

    __metaclass__ = IPFSClientMetaClass
    _clientfactory = IPFSHTTPClient

    CLIENT_ID = 'ipfs'
    VERSION = 1.0

    def __init__(self,
                 host=None,
                 port=None,
                 base=None,
                 default_enc='json',
                 **defaults):

        super(IPFSClient, self).__init__(host=host, port=port,
                                         base=base, default_enc=default_enc,
                                         **defaults)

        self._add = IPFSClientFileCommand('/add')
        self._refs_local = ArgCommand('/refs/local')
        self._bootstrap_list = ArgCommand('/bootstrap/list')

    def build_options(self, node_id, **kwargs):
        return ClientOptions(self.CLIENT_ID, self.VERSION)

    def swarm_connect(self, *args, **kwargs):
        return self._swarm_connect.request(self._client, *args, **kwargs)

    def refs_local(self, **kwargs):
        return self._refs_local.request(self._client, **kwargs)

    def bootstrap_list(self, **kwargs):
        return self._bootstrap_list.request(self._client, **kwargs)

    def get_file(self, multihash, **kwargs):
        return self._get.request(self._client, multihash, **kwargs)

    def get(self, multihash, **kwargs):
        raise NotImplementedError("Please use the get_file method")


class IPFSClientHandler(ClientHandler):

    def __init__(self, config=None):
        super(IPFSClientHandler, self).__init__(IPFSCommands,
                                                config or IPFSConfig())

    def new_client(self):
        return IPFSClient(**self.config.client)

    def command_failed(self, exc, cmd, obj_id, **kwargs):
        logger.error("IPFS: Error executing command '{}': {}"
                     .format(self.commands.names[cmd], exc))


class IPFSAddress(object):

    pattern = '/{}/{}/{}/{}/ipfs/{}'
    pattern_encap = '/{}' + pattern

    min_len = 6
    max_len = 7

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
            return self.pattern_encap.format(ip6 if sa.ipv6 else ip4,
                                             self.ip_address, proto, port,
                                             self.encap_proto, self.node_id)
        else:
            return self.pattern.format(ip6 if sa.ipv6 else ip4,
                                       self.ip_address, proto, port,
                                       self.node_id)

    @staticmethod
    def allowed_ip_address(address):
        return not ip_address_private(address)

    @staticmethod
    def parse(ipfs_address_str):
        """
        Parse an IPFS address string
        :param ipfs_address_str: str: IPFS address string to parse
        :return: IPFSAddress instance
        """
        if not ipfs_address_str:
            raise ValueError('Empty IPFS address')

        min_len = IPFSAddress.min_len + 1
        max_len = IPFSAddress.max_len + 1

        split = ipfs_address_str.split('/')
        split_len = len(split)
        encap = split_len == max_len

        if split_len < min_len or split_len > max_len:
            raise ValueError('Invalid IPFS address')

        # first elem is empty (starting slash)
        split = split[1:]

        return IPFSAddress(
            ip_address=split[1],
            proto=split[2],
            port=split[3],
            encap_proto=split[4] if encap else None,
            node_id=split[-1]
        )
