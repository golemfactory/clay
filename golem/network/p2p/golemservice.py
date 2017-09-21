from devp2p.service import WiredService
from devp2p import slogging

from .golemprotocol import GolemProtocol

log = slogging.get_logger('golem.service')


class GolemService(WiredService):

    # required by WiredService
    wire_protocol = GolemProtocol  # create for each peer
    name = 'golem_service'

    def __init__(self, app):
        super(GolemService, self).__init__(app)
        self.client = None
        self.peer_manager = None
        self.node = None
        self.task_server = None

    def on_wire_protocol_start(self, proto):
        assert isinstance(proto, self.wire_protocol)

        log.debug('----------------------------------')
        log.debug('on_wire_protocol_start', proto=proto)

        proto.peer.node_name = None

        # register callbacks
        proto.receive_get_tasks_callbacks.append(self.receive_get_tasks)
        proto.receive_task_headers_callbacks.append(self.receive_task_headers)
        proto.receive_get_node_name_callbacks.append(self.receive_get_node_name)
        proto.receive_node_name_callbacks.append(self.receive_node_name)

        # do not call send_get_node_name directly here
        import gevent
        gevent.spawn_later(1., proto.send_get_node_name)

    def on_wire_protocol_stop(self, proto):
        assert isinstance(proto, self.wire_protocol)

        log.debug('----------------------------------')
        log.debug('on_wire_protocol_stop', proto=proto)

    def setup(self, client, task_server):
        self.client = client
        self.peer_manager = client.services.peermanager
        self.node = client.node
        self.task_server = task_server

    def get_tasks(self):
        self.peer_manager.broadcast(GolemProtocol, 'get_tasks')

    def remove_task(self, task_id):
        self.peer_manager.broadcast(GolemProtocol, 'remove_task', task_id)

    def receive_get_tasks(self, proto):
        if not self.task_server:
            return

        task_headers = self.task_server.get_task_headers()
        if task_headers:
            proto.send_task_headers(task_headers)

    def receive_task_headers(self, proto, task_headers):
        for t in task_headers:
            self.task_server.add_task_header(t.to_dict())

    def receive_remove_task(self, proto, task_id):
        self.task_server.remove_task_header(task_id)

    def receive_get_node_name(self, proto):
        proto.send_node_name(self.client.config_desc.node_name)

    def receive_node_name(self, proto, node_name):
        proto.peer.node_name = node_name
