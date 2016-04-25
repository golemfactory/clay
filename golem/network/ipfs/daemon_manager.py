import logging

from golem.network.ipfs.client import IPFSCommands, IPFSClientHandler, IPFS_DEFAULT_PORT
from golem.network.transport.tcpnetwork import SocketAddress

__all__ = ['IPFSDaemonManager']
logger = logging.getLogger(__name__)


class IPFSDaemonManager(IPFSClientHandler):
    
    def __init__(self, config=None):
        super(IPFSDaemonManager, self).__init__(config)

        self.node_id = None
        self.public_key = None
        self.port = None
        self.addresses = None
        self.agent_version = None
        self.proto_version = None

        for node in self.config.bootstrap_nodes:
            self.add_bootstrap_node(node)

    def store_info(self, client=None):
        if not client:
            client = self.new_ipfs_client()

        response = self._handle_retries(client.id, IPFSCommands.id, 'id')

        if response and response[0]:
            data = response[0]
            self.node_id = data.get('ID')
            self.public_key = data.get('PublicKey')
            self.addresses = data.get('Addresses')
            self.agent_version = data.get('AgentVersion')
            self.proto_version = data.get('ProtoVersion')

            if self.addresses:
                try:
                    self.port = int(self.addresses[0].split('/')[3])
                except:
                    logger.warn("IPFS: cannot parse port; incompatible IPFS version?")

        return self.node_id

    @staticmethod
    def build_node_address(address, node_id, port=None, proto=None):
        pattern = '/{}/{}/{}/{}/ipfs/{}'
        ip4, ip6 = 'ip4', 'ip6'
        proto = proto or 'tcp'
        port = port or IPFS_DEFAULT_PORT
        sa = SocketAddress(address, port)
        return pattern.format(ip6 if sa.ipv6 else ip4,
                              address, proto, port, node_id)

    def get_metadata(self):
        return {
            'ipfs': {
                'id': self.node_id,
                'port': self.port,
                'version': self.proto_version
            }
        }

    def interpret_metadata(self, metadata, seed_host, seed_port, addresses, async=True):
        ipfs_meta = metadata.get('ipfs')
        if not ipfs_meta:
            return

        ipfs_id = ipfs_meta.get('id')
        ipfs_port = ipfs_meta.get('port', IPFS_DEFAULT_PORT)

        if not ipfs_id:
            return

        for a in addresses:
            if seed_host == a[0] and seed_port == a[1]:
                url = self.build_node_address(a[0], ipfs_id, port=ipfs_port)
                self.add_bootstrap_node(url, async=async)
                return True

        return False

    def add_bootstrap_node(self, url, client=None, async=True):
        if not client:
            client = self.new_ipfs_client()

        def closure():
            self._handle_retries(client.bootstrap_add,
                                 IPFSCommands.bootstrap_add,
                                 url) if url else None
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
