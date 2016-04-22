from golem.network.ipfs.client import IPFSCommands, IPFSClientHandler
from golem.network.transport.tcpnetwork import SocketAddress

__all__ = ['IPFSDaemonManager']


class IPFSDaemonManager(IPFSClientHandler):
    
    def __init__(self, config=None):
        super(IPFSDaemonManager, self).__init__(config)

        self.node_id = None
        self.public_key = None
        self.addresses = None
        self.agent_version = None
        self.proto_version = None

        for node in self.config.bootstrap_nodes:
            self.add_bootstrap_node(node)

    def id(self, client=None):
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

        return self.node_id

    @staticmethod
    def build_node_address(address, node_id, port=4001, proto=None):
        pattern = '/{}/{}/{}/{}/ipfs/{}'
        ip4, ip6 = 'ip4', 'ip6'
        proto = proto if proto else 'tcp'
        sa = SocketAddress(address, port)
        return pattern.format(ip6 if sa.ipv6 else ip4,
                              address, proto, port, node_id)

    def get_metadata(self):
        return {
            'ipfs': {
                'id': self.node_id,
                'version': self.proto_version
            }
        }

    def add_bootstrap_node(self, url, client=None):
        if not client:
            client = self.new_ipfs_client()
        return self._handle_retries(client.bootstrap_add,
                                    IPFSCommands.bootstrap_add,
                                    url) if url else None

    def remove_bootstrap_node(self, url, client=None):
        if not client:
            client = self.new_ipfs_client()
        return self._handle_retries(client.bootstrap_rm,
                                    IPFSCommands.bootstrap_rm,
                                    url) if url else None

    def list_bootstrap_nodes(self, client=None):
        if not client:
            client = self.new_ipfs_client()

        result = self._handle_retries(client.bootstrap_list,
                                      IPFSCommands.bootstrap_list,
                                      obj_id=IPFSCommands.bootstrap_list)

        if result and result[0]:
            return result[0].get('Peers', [])
        return []
