import logging

import ipaddress

from golem.core.common import to_unicode
from golem.network.ipfs.client import IPFSCommands, IPFSClientHandler, IPFSAddress

__all__ = ['IPFSDaemonManager']
logger = logging.getLogger(__name__)

MAX_IPFS_ADDRESSES_PER_NODE = 8


class IPFSDaemonManager(IPFSClientHandler):

    def __init__(self, config=None, connect_to_bootstrap_nodes=True):
        super(IPFSDaemonManager, self).__init__(config)

        self.node_id = None
        self.public_key = None
        self.agent_version = None
        self.proto_version = None
        self.addresses = []
        self.meta_addresses = []
        self.bootstrap_nodes = set()

        if connect_to_bootstrap_nodes:
            for node in self.config.bootstrap_nodes:
                try:
                    self.add_bootstrap_node(node, async=False)
                    self.swarm_connect(node)
                except Exception as e:
                    logger.error('IPFS: Error adding bootstrap node {}: {}'
                                 .format(node, e.message))

            self.bootstrap_nodes = set(self.list_bootstrap_nodes())

    def store_client_info(self, client=None):
        if not client:
            client = self.new_client()

        response = self._handle_retries(client.id, IPFSCommands.id)

        if response:
            self.node_id = response.get('ID')
            self.public_key = response.get('PublicKey')
            self.addresses = [IPFSAddress.parse(a) for a in response.get('Addresses')]
            self.agent_version = response.get('AgentVersion')
            self.proto_version = response.get('ProtoVersion')

            for ipfs_addr in self.addresses:
                # filter out private addresses
                if IPFSAddress.allowed_ip_address(ipfs_addr.ip_address):
                    self.meta_addresses.append(str(ipfs_addr))

        return self.node_id

    def get_metadata(self):
        return {
            'ipfs': {
                'addresses': self.meta_addresses,
                'version': self.proto_version
            }
        }

    def connect_to_bootstrap_nodes(self, client=None, async=True):
        for bootstrap_node in self.bootstrap_nodes:
            self.swarm_connect(bootstrap_node, client=client, async=async)

    def interpret_metadata(self, metadata, seed_addresses, node_addresses, async=True):
        ipfs_meta = metadata.get('ipfs')
        if not ipfs_meta:
            return False

        ipfs_addresses = ipfs_meta['addresses']
        if not ipfs_addresses:
            return False

        added = False

        for address in node_addresses:
            for seed_address in seed_addresses:
                if seed_address[0] == address[0] and seed_address[1] == address[1]:
                    added = self._add_bootstrap_addresses(seed_address[0],
                                                          ipfs_addresses,
                                                          async=async) or added
        return added

    def add_bootstrap_node(self, url, client=None, async=True):
        if not client:
            client = self.new_client()
        return self._node_action(url,
                                 async=async,
                                 method=client.bootstrap_add,
                                 command=IPFSCommands.bootstrap_add,
                                 success=self.__add_bootstrap_node_success,
                                 error=self.__add_bootstrap_node_error,
                                 obj_id=url)

    def remove_bootstrap_node(self, url, client=None, async=True):
        if not client:
            client = self.new_client()
        return self._node_action(url,
                                 async=async,
                                 method=client.bootstrap_rm,
                                 command=IPFSCommands.bootstrap_rm,
                                 success=self.__remove_bootstrap_node_success,
                                 error=self.__remove_bootstrap_node_error,
                                 obj_id=url)

    def swarm_connect(self, url, client=None, async=True):
        if not client:
            client = self.new_client()
        return self._node_action(url,
                                 async=async,
                                 method=client.swarm_connect,
                                 command=IPFSCommands.swarm_connect,
                                 success=self.__swarm_connect_success,
                                 error=self.__swarm_connect_error,
                                 obj_id=url)

    def swarm_disconnect(self, url, client=None, async=True):
        if not client:
            client = self.new_client()
        return self._node_action(url,
                                 async=async,
                                 method=client.swarm_disconnect,
                                 command=IPFSCommands.swarm_disconnect,
                                 success=self.__swarm_disconnect_success,
                                 error=self.__swarm_disconnect_error,
                                 obj_id=url)

    def swarm_peers(self, client=None):
        if not client:
            client = self.new_client()
        try:
            return self._handle_retries(
                client.swarm_peers,
                IPFSCommands.swarm_peers
            )
        except Exception as exc:
            logger.error("IPFS: Cannot list swarm peers: {}".format(exc))
        return []

    def list_bootstrap_nodes(self, client=None):
        if not client:
            client = self.new_client()

        result = self._handle_retries(client.bootstrap_list,
                                      IPFSCommands.bootstrap_list)

        if result:
            return result.get('Peers', [])
        return []

    def _node_action(self, url, method, command, success, error, obj_id=None, async=True):
        def closure(*_):
            self._handle_retries(method, command, url,
                                 obj_id=obj_id,
                                 raise_exc=True)
            if success:
                success(url)
            return url

        if async:
            self._async_call(closure, success, error,
                             obj_id=obj_id)
        else:
            try:
                return closure()
            except Exception as exc:
                error(exc)
        return None

    def _add_bootstrap_addresses(self, seed_ip_str, ipfs_address_strs, async=True):
        seed_ip_addr = self._ip_from_str(seed_ip_str)
        urls = set()

        for ipfs_address_str in ipfs_address_strs:
            ipfs_address = IPFSAddress.parse(ipfs_address_str)
            ipfs_ip_addr = self._ip_from_str(ipfs_address.ip_address)

            if type(seed_ip_addr) is type(ipfs_ip_addr):
                ipfs_address.ip_address = seed_ip_str
                urls.add(str(ipfs_address))

        for url in urls:
            if url not in self.bootstrap_nodes:
                self.add_bootstrap_node(url, async=async)
                self.swarm_connect(url)

        return len(urls) > 0

    @staticmethod
    def _ip_from_str(ip_address):
        return ipaddress.ip_address(to_unicode(ip_address))

    def __add_bootstrap_node_success(self, url):
        logger.debug("IPFS: Added bootstrap node: {}".format(url))
        self.bootstrap_nodes.add(url)

    @staticmethod
    def __add_bootstrap_node_error(exc, *args):
        logger.error("IPFS: Error adding bootstrap node: {}".format(exc))

    def __remove_bootstrap_node_success(self, url):
        logger.debug("IPFS: Removed bootstrap node: {}".format(url))
        if url in self.bootstrap_nodes:
            self.bootstrap_nodes.remove(url)

    @staticmethod
    def __remove_bootstrap_node_error(exc, *args):
        logger.error("IPFS: Error removing bootstrap node: {}".format(exc))

    @staticmethod
    def __swarm_connect_success(url):
        logger.debug("IPFS: Connected to node: {}".format(url))

    @staticmethod
    def __swarm_connect_error(exc, *args):
        logger.debug("IPFS: Error connecting to node: {}".format(exc))

    @staticmethod
    def __swarm_disconnect_success(url):
        logger.debug("IPFS: Disconnecting from node: {}".format(url))

    @staticmethod
    def __swarm_disconnect_error(exc, *args):
        logger.debug("IPFS: Error disconnecting from node: {}".format(exc))
