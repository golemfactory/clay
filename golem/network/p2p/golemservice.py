from devp2p.service import WiredService
from golemprotocol import GolemProtocol
from ethereum import slogging
log = slogging.get_logger('golem.service')


class GolemService(WiredService):

    # required by WiredService
    wire_protocol = GolemProtocol  # create for each peer

    name = 'golemservice'

    def __init__(self, client):
        self.client = client
        super(GolemService, self).__init__(client)

    def on_wire_protocol_start(self, proto):
        log.debug('----------------------------------')
        log.debug('on_wire_protocol_start', proto=proto)
        assert isinstance(proto, self.wire_protocol)
        # register callbacks
        proto.receive_get_tasks_callbacks.append(self.on_receive_get_tasks)
        proto.receive_task_headers_callbacks.append(self.on_receive_task_headers)

    def on_wire_protocol_stop(self, proto):
        assert isinstance(proto, self.wire_protocol)
        log.debug('----------------------------------')
        log.debug('on_wire_protocol_stop', proto=proto)

    def set_task_server(self, task_server):
        self.task_server = task_server

    def get_tasks(self):
        self.client.services.peermanager.broadcast(GolemProtocol,
                   'get_tasks' )

    def on_receive_get_tasks(self, proto):
        log.info("GetTasks got")
        l = self.task_server.get_tasks_headers()
        if len(l) > 0:
            proto.send_task_headers(l)
        else:
            print "no tasks"

    def on_receive_task_headers(self, proto, task_headers):
        pass