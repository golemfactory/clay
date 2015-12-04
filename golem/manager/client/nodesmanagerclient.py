
from clientmanagersession import ClientManagerSessionFactory
from golem.network.transport.tcpnetwork import TCPNetwork, TCPAddress, TCPConnectInfo
from golem.network.transport.network import ProtocolFactory
from golem.manager.managerconnstate import ManagerConnState

import logging

logger = logging.getLogger(__name__)


class NodesManagerClient:


    def __init__(self, manager_server_address, manager_server_port):
        self.manager_server_address    = manager_server_address
        self.manager_server_port       = manager_server_port
        self.client_manager_session   = None

        self.network = TCPNetwork(ProtocolFactory(ManagerConnState, None, ClientManagerSessionFactory()))

    def start(self):
        try:
            if (int(self.manager_server_port) < 1) or (int(self.manager_server_port) > 65535):
                logger.warning(u"Manager Server port number out of range [1, 65535]: {}".format(self.manager_server_port))
                return True
        except Exception, e:
            logger.error(u"Wrong seed port number {}: {}".format(self.manager_server_port, str(e)))
            return True

        if not self.client_manager_session:
            self.__connect_nodes_manager()

    def send_client_state_snapshot(self, snapshot):
        if self.client_manager_session:
            self.client_manager_session.send_client_state_snapshot(snapshot)
        else:
            logger.error("No client_manager_session defined")

    def dropConnection(self):
        if  self.client_manager_session:
            self.client_manager_session.dropped()

    def add_new_task(self, task):
        pass

    def run_new_nodes(self, num):
        pass

    def __connect_nodes_manager(self):

        assert not self.client_manager_session # connection already established

        connect_info = TCPConnectInfo([TCPAddress(self.manager_server_address, self.manager_server_port)], self.__connection_established, self.__connection_failure)
        self.network.connect(connect_info)

    def __connection_established(self, session):
        session.client = self
        self.client_manager_session = session

    def __connection_failure(self):
        logger.error("Connection to nodes manager failure.")


class NodesManagerUidClient (NodesManagerClient):
    def __init__(self, node_name, manager_server_address, manager_server_port, task_manager, logic = None):
        NodesManagerClient.__init__(self, manager_server_address, manager_server_port)
        self.node_name              = node_name
        self.logic                  = logic
        self.task_manager            = task_manager

    def add_new_task(self, task):
        if self.logic:
            self.logic.add_task_from_definition(task)
        elif self.task_manager:
            task.return_address  = self.task_manager.listen_address
            task.return_port     = self.task_manager.listen_port
            task.task_owner = self.task_manager.node
            self.task_manager.add_new_task(task)
        else:
            logger.error("No logic and no task_manager defined.")

    def run_new_nodes(self, num):
        self.logic.add_new_nodes_function(num)
