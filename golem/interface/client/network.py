from golem.core.deferred import sync_wait
from golem.interface.command import group, Argument, command, CommandResult, doc
from golem.network.transport.tcpnetwork import SocketAddress


@group(help="Manage network")
class Network(object):

    client = None

    node_table_headers = ['ip', 'port', 'id', 'name']

    ip_arg = Argument('ip', help='Remote IP address')
    port_arg = Argument('port', help='Remote TCP port')

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

    @command(arguments=(ip_arg, port_arg), help="Connect to a node")
    def connect(self, ip, port):
        try:
            sa = SocketAddress(ip, int(port))
            Network.client.connect((sa.address, sa.port))
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
            values.append([
                str(peer['address']),
                str(peer['port']),
                Network.__key_id(peer['key_id'], full),
                unicode(peer['node_name'])
            ])

        return CommandResult.to_tabular(Network.node_table_headers, values,
                                        sort=sort)

    @staticmethod
    def __key_id(key_id, full=False):
        if full:
            return key_id
        return key_id[:16] + "..." + key_id[-16:]
