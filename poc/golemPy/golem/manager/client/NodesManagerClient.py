
from ClientManagerSession import ClientManagerSessionFactory
from golem.network.transport.tcp_network import TCPNetwork, TCPAddress, TCPConnectInfo
from golem.network.transport.network import ProtocolFactory
from golem.manager.ManagerConnState import ManagerConnState

import logging

logger = logging.getLogger(__name__)

class NodesManagerClient:

    ######################
    def __init__(self, managerServerAddress, managerServerPort):
        self.managerServerAddress    = managerServerAddress
        self.managerServerPort       = managerServerPort
        self.clientManagerSession   = None

        self.network = TCPNetwork(ProtocolFactory(ManagerConnState, None, ClientManagerSessionFactory()))

    ######################
    def start(self):
        try:
            if (int(self.managerServerPort) < 1) or (int(self.managerServerPort) > 65535):
                logger.warning(u"Manager Server port number out of range [1, 65535]: {}".format(self.managerServerPort))
                return True
        except Exception, e:
            logger.error(u"Wrong seed port number {}: {}".format(self.managerServerPort, str(e)))
            return True

        if not self.clientManagerSession:
            self.__connectNodesManager()

    #############################
    def sendClientStateSnapshot(self, snapshot):
        if self.clientManagerSession:
            self.clientManagerSession.sendClientStateSnapshot(snapshot)
        else:
            logger.error("No clientManagerSession defined")

    ######################
    def dropConnection(self):
        if  self.clientManagerSession:
            self.clientManagerSession.dropped()

    #############################
    def addNewTask(self, task):
        pass

    ######################
    def runNewNodes(self, num):
        pass

    ######################
    def __connectNodesManager(self):

        assert not self.clientManagerSession # connection already established

        connect_info = TCPConnectInfo([TCPAddress(self.managerServerAddress, self.managerServerPort)], self.__connection_established, self.__connection_failure)
        self.network.connect(connect_info)

    #############################
    def __connection_established(self, session):
        session.client = self
        self.clientManagerSession = session

    def __connection_failure(self):
        logger.error("Connection to nodes manager failure.")

class NodesManagerUidClient (NodesManagerClient):
    ######################
    def __init__(self, client_uid, managerServerAddress, managerServerPort, task_manager, logic = None):
        NodesManagerClient.__init__(self, managerServerAddress, managerServerPort)
        self.client_uid              = client_uid
        self.logic                  = logic
        self.task_manager            = task_manager

    ######################
    def addNewTask(self, task):
        if self.logic:
            self.logic.addTaskFromDefinition(task)
        elif self.task_manager:
            task.returnAddress  = self.task_manager.listenAddress
            task.returnPort     = self.task_manager.listenPort
            task.taskOwner = self.task_manager.node
            self.task_manager.addNewTask(task)
        else:
            logger.error("No logic and no task_manager defined.")

    ######################
    def runNewNodes(self, num):
        self.logic.addNewNodesFunction(num)
