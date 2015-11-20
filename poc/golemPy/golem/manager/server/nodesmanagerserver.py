from golem.network.transport.tcpnetwork import TCPNetwork, TCPListenInfo
from golem.network.transport.network import ProtocolFactory
from golem.manager.nodestatesnapshot import NodeStateSnapshot
from servermanagersession import ServerManagerSessionFactory
import logging

logger = logging.getLogger(__name__)


class NodesManagerServer:
    def __init__(self, nodes_manager, port, reactor=None):
        self.port = port
        self.manager_sessions = []
        self.reactor = reactor
        self.nodes_manager = nodes_manager

        self.network = TCPNetwork(ProtocolFactory(ManagerConnState, self, ServerManagerSessionFactory(self)))

        self.__start_accepting()

    def set_reactor(self, reactor):
        self.reactor = reactor

    def __start_accepting(self):
        listen_info = TCPListenInfo(self.port, established_callback=self.__listening_established,
                                    failure_callback=self.__listening_failure)
        self.network.listen(listen_info)

    def __listening_established(self, port, **kwargs):
        logger.info("Manager server - port {} opened, listening".format(port))

    def __listening_failure(self, **kwargs):
        logger.error("Opening {} port for listening failed - bailign out".format(self.port))

    def new_connection(self, session):
        self.manager_sessions.append(session)

    def node_state_snapshot_received(self, nss):
        self.nodes_manager.append_state_update(nss)

    def manager_session_disconnect(self, uid):
        self.nodes_manager.append_state_update(NodeStateSnapshot(False, uid))

    def send_terminate(self, uid):
        for ms in self.manager_sessions:
            if ms.uid == uid:
                ms.send_kill_node()

    def send_terminate_all(self, uid):
        for ms in self.manager_sessions:
            if ms.uid == uid:
                ms.send_kill_all_nodes()

    def send_new_task(self, uid, task):
        for ms in self.manager_sessions:
            if ms.uid == uid:
                ms.send_new_task(task)

    def send_new_nodes(self, uid, num_nodes):
        for ms in self.manager_sessions:
            if ms.uid == uid:
                ms.send_new_nodes(num_nodes)


from twisted.internet.protocol import Factory
from golem.manager.managerconnstate import ManagerConnState


class ManagerServerFactory(Factory):
    def __init__(self, server):
        self.server = server

    def buildProtocol(self, addr):
        return ManagerConnState(self.server)
