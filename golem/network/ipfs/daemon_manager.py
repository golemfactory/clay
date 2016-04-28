import logging

import ipaddress

from golem.network.ipfs.client import IPFSCommands, IPFSClientHandler, IPFSAddress

__all__ = ['IPFSDaemonManager']
logger = logging.getLogger(__name__)

MAX_IPFS_ADDRESSES_PER_NODE = 8


def to_unicode(source):
    if not isinstance(source, unicode):
        return unicode(source)
    return source


class IPFSDaemonManager(IPFSClientHandler):

    def __init__(self, config=None):
        super(IPFSDaemonManager, self).__init__(config)

        self.node_id = None
        self.public_key = None
        self.port = None
        self.addresses = None
        self.agent_version = None
        self.proto_version = None
        self.meta_addresses = None

        for node in self.config.bootstrap_nodes:
            try:
                self.add_bootstrap_node(node, async=False)
            except Exception as e:
                logger.error('IPFS: Error adding bootstrap node {}: {}'
                             .format(node, e.message))

    def store_client_info(self, client=None):
        if not client:
            client = self.new_ipfs_client()

        response = self._handle_retries(client.id, IPFSCommands.id, 'id')

        if response and response[0]:
            data = response[0]
            self.node_id = data.get('ID')
            self.public_key = data.get('PublicKey')
            self.addresses = [IPFSAddress.parse(a) for a in data.get('Addresses')]
            self.agent_version = data.get('AgentVersion')
            self.proto_version = data.get('ProtoVersion')

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
            self.add_bootstrap_node(url, async=async)
        return len(urls) > 0

    @staticmethod
    def _ip_from_str(ip_address):
        return ipaddress.ip_address(to_unicode(ip_address))

    def add_bootstrap_node(self, url, client=None, async=True):
        if not client:
            client = self.new_ipfs_client()

        def closure():
            try:
                self._handle_retries(client.bootstrap_add,
                                     IPFSCommands.bootstrap_add,
                                     url) if url else None
            except Exception as e:
                logger.error("IPFS: error adding bootstrap node {}: {}"
                             .format(url, e.message))
            return url

        if async:
            self._ipfs_async_call(closure,
                                  self.__add_bootstrap_node_success,
                                  self.__add_bootstrap_node_error)
        else:
            return closure()

    def remove_bootstrap_node(self, url, client=None, async=True):
        if not client:
            client = self.new_ipfs_client()

        def closure():
            self._handle_retries(client.bootstrap_rm,
                                 IPFSCommands.bootstrap_rm,
                                 url) if url else None
            return url

        if async:
            self._ipfs_async_call(closure,
                                  self.__remove_bootstrap_node_success,
                                  self.__remove_bootstrap_node_error)
        else:
            return closure()

    @staticmethod
    def __add_bootstrap_node_success(url):
        logger.debug("IPFS: Added bootstrap node {}".format(url))

    @staticmethod
    def __add_bootstrap_node_error(exc, *args):
        logger.error("IPFS: Error adding bootstrap node: {}".format(exc))

    @staticmethod
    def __remove_bootstrap_node_success(url):
        logger.debug("IPFS: Removed bootstrap node {}".format(url))

    @staticmethod
    def __remove_bootstrap_node_error(exc, *args):
        logger.error("IPFS: Error removing bootstrap node: {}".format(exc))

    def list_bootstrap_nodes(self, client=None):
        if not client:
            client = self.new_ipfs_client()

        result = self._handle_retries(client.bootstrap_list,
                                      IPFSCommands.bootstrap_list,
                                      obj_id=IPFSCommands.bootstrap_list)

        if result and result[0]:
            return result[0].get('Peers', [])
        return []
