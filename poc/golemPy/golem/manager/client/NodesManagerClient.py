
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

        connect_info = TCPConnectInfo([TCPAddress(self.managerServerAddress, self.managerServerPort)], self.__connectionEstablished, self.__connectionFailure)
        self.network.connect(connect_info)

    #############################
    def __connectionEstablished(self, session):
        session.client = self
        self.clientManagerSession = session

    def __connectionFailure(self):
        logger.error("Connection to nodes manager failure.")

class NodesManagerUidClient (NodesManagerClient):
    ######################
    def __init__(self, clientUid, managerServerAddress, managerServerPort, taskManager, logic = None):
        NodesManagerClient.__init__(self, managerServerAddress, managerServerPort)
        self.clientUid              = clientUid
        self.logic                  = logic
        self.taskManager            = taskManager

    ######################
    def addNewTask(self, task):
        if self.logic:
            self.logic.addTaskFromDefinition(task)
        elif self.taskManager:
            task.returnAddress  = self.taskManager.listenAddress
            task.returnPort     = self.taskManager.listenPort
            task.taskOwner = self.taskManager.node
            self.taskManager.addNewTask(task)
        else:
            logger.error("No logic and no taskManager defined.")

    ######################
    def runNewNodes(self, num):
        self.logic.addNewNodesFunction(num)
