import logging
import os
import subprocess

import ipfsapi
import shutil
from enum import Enum
from ipfsapi.exceptions import CommunicationError, EncoderError
from requests import HTTPError

from golem.core.hostaddress import ip_address_private
from golem.network.transport.tcpnetwork import SocketAddress
from golem.resource.client import ClientConfig, ClientHandler, IClient, ClientOptions

logger = logging.getLogger(__name__)

IPFS_DEFAULT_TCP_PORT = 4001
IPFS_DEFAULT_UDP_PORT = 4002

IPFS_BOOTSTRAP_NODES = [
    '/ip4/94.23.17.170/tcp/4001/ipfs/QmXR8NZWUJhsbixGmeNoC6DxJQxySCP3BEHRm3mbk8Yv7G',
    '/ip4/52.40.149.71/tcp/4001/ipfs/QmX47BhziLbt3CVYsSmrH5xGfQM1t2T5De2XFZFfR4EBWr',
    '/ip4/52.40.149.24/tcp/4001/ipfs/QmNSjTqoyieCCBPBMGeSzzg3C4SNUDuqg8ob16L83X4WRf'
]


class IPFSCommands(Enum):

    add = 0
    get = 1
    id = 2
    pin_add = 3
    pin_rm = 4

    bootstrap_add = 5
    bootstrap_rm = 6
    bootstrap_list = 7

    swarm_connect = 8
    swarm_disconnect = 9
    swarm_peers = 10


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


class IPFSClient(IClient):

    CLIENT_ID = 'ipfs'
    VERSION = 1.1

    def __init__(self, **kwargs):
        self._api = ipfsapi.connect(**kwargs)

    @staticmethod
    def build_options(node_id, **kwargs):
        return ClientOptions(IPFSClient.CLIENT_ID, IPFSClient.VERSION, **kwargs)

    def get_file(self, multihash, client_options=None, **kwargs):
        file_path = kwargs.get('filepath')
        file_name = kwargs.pop('filename')

        if not os.path.exists(file_path):
            os.makedirs(file_path)

        self.get(multihash, **kwargs)

        file_src = os.path.join(file_path, multihash)
        file_dst = os.path.join(file_path, file_name)
        shutil.move(file_src, file_dst)

        return dict(Name=file_dst, Hash=multihash)

    def __getattribute__(self, attr):
        if attr in IPFSCommands.__members__:
            method = getattr(self._api, attr)

            def wrapper(*args, **kwargs):
                kwargs.pop('client_options', None)
                try:
                    return method(*args, **kwargs)
                except (CommunicationError, EncoderError) as e:
                    raise HTTPError(e)

            return wrapper

        return object.__getattribute__(self, attr)


class IPFSClientHandler(ClientHandler):

    def __init__(self, config=None):
        super(IPFSClientHandler, self).__init__(IPFSCommands,
                                                config or IPFSConfig())

    def new_client(self):
        return IPFSClient(**self.config.client)

    def command_failed(self, exc, cmd, obj_id, **kwargs):
        logger.error("IPFS: Error executing command '{}': {}"
                     .format(cmd.name, exc))


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


def ipfs_running():
    try:
        result = subprocess.check_call(['ipfs', 'swarm', 'peers'])
    except Exception:
        return False
    return result == 0
