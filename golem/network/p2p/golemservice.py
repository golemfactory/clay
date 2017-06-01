from devp2p.service import WiredService
from golemprotocol import GolemProtocol
from ethereum import slogging
from ethereum.utils import encode_hex
log = slogging.get_logger('golem.service')

class GolemService(WiredService):

    # required by WiredService
    wire_protocol = GolemProtocol  # create for each peer

    name = 'golemservice'

    def __init__(self, client):
        self.client = client
        self.node = client.node
        self.suggested_conn_reverse = {}
        self.suggested_address = {}
        super(GolemService, self).__init__(client)

    def on_wire_protocol_start(self, proto):
        log.debug('----------------------------------')
        log.debug('on_wire_protocol_start', proto=proto)
        assert isinstance(proto, self.wire_protocol)
        # register callbacks
        self.suggested_address[encode_hex(proto.peer.remote_pubkey)]\
            = proto.peer.ip_port[0]
        proto.receive_get_tasks_callbacks.append(self.on_receive_get_tasks)
        proto.receive_task_headers_callbacks.append(self.on_receive_task_headers)
        proto.receive_want_to_start_task_session_callbacks.append(self.on_receive_want_to_start_task_session)
        proto.receive_set_task_session_callbacks.append(self.on_receive_set_task_session)

    def on_wire_protocol_stop(self, proto):
        assert isinstance(proto, self.wire_protocol)
        log.debug('----------------------------------')
        log.debug('on_wire_protocol_stop', proto=proto)
        self.suggested_address.pop(encode_hex(proto.peer.remote_pubkey), None)
        self.suggested_conn_reverse.pop(encode_hex(proto.peer.remote_pubkey), None)

    def set_task_server(self, task_server):
        self.task_server = task_server

    def get_tasks(self):
        self.client.services.peermanager.broadcast(GolemProtocol,
                   'get_tasks' )

    def on_receive_get_tasks(self, proto):
        l = self.task_server.get_tasks_headers()
        if len(l) > 0:
            proto.send_task_headers(l)

    def on_receive_task_headers(self, proto, task_headers):
        for t in task_headers:
            self.task_server.add_task_header(t.to_dict())

    def want_to_start_task_session(self, key_id, node, conn_id, super_node_info=None):
        """ Inform peer with public key <key_id> that node from node info want to start task session with him. If
                peer with given id is on a list of peers that this message will be send directly. Otherwise all peers will
                receive a request to pass this message.
                :param str key_id: key id of a node that should open a task session
                :param Node node_info: information about node that requested session
                :param str conn_id: connection id for reference
                :param Node|None super_node_info: *Default: None* information about node with public ip that took part
                in message transport
                """
        if not self.task_server.task_connections_helper.is_new_conn_request(
                conn_id, key_id, node, super_node_info):
            # fixme
            self.task_server.remove_pending_conn(conn_id)
            self.task_server.remove_responses(conn_id)
            return

        if super_node_info is None and self.node.is_super_node():
            super_node_info = self.node

        connected_peer = None
        peers = self.app.services.peermanager.peers
        for peer in peers:
            if key_id == encode_hex(peer.remote_pubkey):
                connected_peer = peer

        if connected_peer:
            if node.key == self.node.key:
                self.set_suggested_conn_reverse(key_id)
            connected_peer.protocols[GolemProtocol].send_want_to_start_task_session(node, conn_id, super_node_info)
            return

        msg_snd = False
        for peer in peers:
            if encode_hex(peer.remote_pubkey) != node.key:
                peer.protocols[GolemProtocol].send_set_task_session(key_id, node, conn_id, super_node_info)
                msg_snd = True

        if msg_snd and node.key == self.node.key:
            self.task_server.add_forwarded_session_request(key_id, conn_id)

        # TODO This method should be only sent to supernodes or nodes that are closer to the target node

        if not msg_snd and node.key == self.node.key:
            self.task_server.task_connections_helper.cannot_start_task_session(conn_id)

    def set_suggested_conn_reverse(self, client_key_id, value=True):
        self.suggested_conn_reverse[client_key_id] = value

    def get_suggested_conn_reverse(self, client_key_id):
        return self.suggested_conn_reverse.get(client_key_id, False)

    def on_receive_want_to_start_task_session(self, proto, node, connection_id, super_node):
        self.task_server.start_task_session(node, super_node, connection_id)

    def on_receive_set_task_session(self, proto, key, node, connection_id, super_node):
        self.want_to_start_task_session(key, node, connection_id, super_node)

    def remove_task(self, task_id):
        self.client.services.peermanager.broadcast(GolemProtocol,
                   'remove_task', (task_id) )

    def on_receive_remove_task(self, proto, task_id):
        self.task_server.remove_task_header(task_id)