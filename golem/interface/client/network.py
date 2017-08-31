from golem.core.deferred import sync_wait
from golem.interface.command import group, Argument, command, CommandResult, doc
from golem.network.transport.tcpnetwork import SocketAddress
from ethereum.utils import encode_hex

@group(help="Manage network")
class Network(object):

    client = None

    node_table_headers = ['ip', 'port', 'id', 'version']

    ip_arg = Argument('ip', help='Remote IP address')
    port_arg = Argument('port', help='Remote port address')
    node_id_arg = Argument('node_id', help='Remote node_id address')

    full_table = Argument(
        '--full',
        optional=True,
        help="Show full table contents"
    )
    sort_nodes = Argument(
        '--sort',
        choices=node_table_headers,
        optional=True,
        help="Sort nodes"
    )

    @doc("Show client status")
    def status(self):
        deferred = Network.client.connection_status()
        status = sync_wait(deferred) or "unknown"
        return status

    @command(arguments=(ip_arg, port_arg, node_id_arg), help="Connect to a node")
    def connect(self, ip, port, node_id):
        try:
            sa = SocketAddress(ip, int(port))
            Network.client.connect((sa.address, sa.port), node_id)
        except Exception as exc:
            return CommandResult(error="Cannot connect to {}:{}: {}"
                                       .format(ip, port, exc))

    @command(arguments=(sort_nodes, full_table), help="Show connected nodes")
    def show(self, sort, full):
        deferred = Network.client.get_connected_peers()
        peers = sync_wait(deferred) or []
        return self.__peers(peers, sort, full)

    @command(arguments=(sort_nodes, full_table), help="Show known nodes")
    def dht(self, sort, full):
        deferred = Network.client.get_known_peers()
        peers = sync_wait(deferred) or []
        return self.__peers(peers, sort, full)

    @staticmethod
    def __peers(peers, sort, full):
        values = []

        for peer in peers:
            ip = peer['ip_port'][0]
            port = str(peer['ip_port'][1])
            values.append([
                str(ip),
                port,
                Network.__key_id(encode_hex(peer['remote_pubkey']), full),
                str(peer['node_name'])
            ])

        return CommandResult.to_tabular(Network.node_table_headers, values,
                                        sort=sort)

    @staticmethod
    def __one_of(dictionary, *keys):
        for key in keys:
            value = dictionary.get(key)
            if value is not None:
                return value

    @staticmethod
    def __key_id(key_id, full=False):
        if full:
            return key_id
        return key_id[:16] + b"..." + key_id[-16:]
