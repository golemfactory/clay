from golem.network.transport.tcp_network import TCPNetwork, TCPListenInfo
from golem.network.transport.network import ProtocolFactory
from golem.manager.NodeStateSnapshot import NodeStateSnapshot
from ServerManagerSession import  ServerManagerSessionFactory
import logging

logger = logging.getLogger(__name__)

class NodesManagerServer:

    #############################
    def __init__(self, nodesManager, port, reactor = None):
        self.port               = port
        self.manager_sessions    = []
        self.reactor            = reactor
        self.nodesManager       = nodesManager

        self.network = TCPNetwork(ProtocolFactory(ManagerConnState, self, ServerManagerSessionFactory(self)))

        self.__start_accepting()

    #############################
    def setReactor(self, reactor):
        self.reactor = reactor

    #############################
    def __start_accepting(self):
        listen_info = TCPListenInfo(self.port, established_callback=self.__listeningEstablished,
                      failure_callback=self.__listeningFailure)
        self.network.listen(listen_info)


    #############################
    def __listeningEstablished(self, port, **kwargs):
        logger.info("Manager server - port {} opened, listening".format(port))

    #############################
    def __listeningFailure(self, **kwargs):
        logger.error("Opening {} port for listening failed - bailign out".format(self.port))

    #############################
    def newConnection(self, session):
        self.manager_sessions.append(session)

    #############################
    def nodeStateSnapshotReceived(self, nss):
        self.nodesManager.appendStateUpdate(nss)
        
    #############################
    def manager_session_disconnect(self, uid):
        self.nodesManager.appendStateUpdate(NodeStateSnapshot(False, uid))

    #############################
    def sendTerminate(self, uid):
        for ms in self.manager_sessions:
            if ms.uid == uid:
                ms.sendKillNode()

    def sendTerminateAll(self, uid):
        for ms in self.manager_sessions:
            if ms.uid == uid:
                ms.sendKillAllNodes()

    #############################
    def sendNewTask(self, uid, task):
        for ms in self.manager_sessions:
            if ms.uid == uid:
                ms.sendNewTask(task)


    #############################
    def sendNewNodes(self, uid, numNodes):
        for ms in self.manager_sessions:
            if ms.uid == uid:
                ms.sendNewNodes(numNodes)


from twisted.internet.protocol import Factory
from golem.manager.ManagerConnState import ManagerConnState

class ManagerServerFactory(Factory):
    #############################
    def __init__(self, server):
        self.server = server

    #############################
    def buildProtocol(self, addr):
        return ManagerConnState(self.server)

