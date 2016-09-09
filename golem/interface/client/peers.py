from golem.interface.command import group, Argument, command, CommandHelper, CommandResult


@group(help="Peer management commands")
class Peers(object):

    client = None

    peer_table_headers = ['ip', 'port', 'id', 'name']

    full_table = Argument(
        '--full',
        boolean=True,
        optional=True,
        help="Show full table contents"
    )

    sort_peers = Argument(
        '--sort',
        choices=peer_table_headers,
        optional=True,
        help="Sort peers"
    )

    @command(arguments=(sort_peers, full_table), help="Show connected peers")
    def show(self, sort, full):
        values = []

        deferred = Peers.client.get_peer_info()
        peers = CommandHelper.wait_for(deferred)

        if peers:
            values = [[unicode(p.address), unicode(p.port),
                       Peers.__key_id(p.key_id, full),
                       unicode(p.node_name)] for p in peers]

            values = CommandResult.sort(Peers.peer_table_headers, values, sort)

        return CommandResult.to_tabular(Peers.peer_table_headers, values)

    @staticmethod
    def __key_id(key_id, full=False):
        if full:
            return unicode(key_id)
        else:
            return unicode(key_id[:16]) + u"..." + unicode(key_id[-16:])
