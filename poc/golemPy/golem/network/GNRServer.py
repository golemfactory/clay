import logging
import time
import uuid

from collections import deque

from golem.network.transport.Tcp import Network, HostData, nodeInfoToHostInfos

logger = logging.getLogger(__name__)

#######################################################################################
class GNRServer:
    #############################
    def __init__(self, configDesc, factory, useIp6=False):
        self.configDesc = configDesc
        self.factory = factory

        self.curPort = 0
        self.iListeningPort = None

        self._startAccepting(useIp6)

    #############################
    def newConnection(self, session):
        pass

    #############################
    def changeConfig(self, configDesc):
        self.configDesc = configDesc

        if self.iListeningPort is None:
            self._startAccepting()
            return

        if self.iListeningPort and (configDesc.startPort > self.curPort or configDesc.endPort < self.curPort):
            self.iListeningPort.stopListening()
            self._startAccepting()

    #############################
    def _startAccepting(self, useIp6=False):
        logger.info("Enabling network accepting state")

        Network.listen(self.configDesc.startPort, self.configDesc.endPort, self._getFactory(), None, self._listeningEstablished, self._listeningFailure, useIp6)

    #############################
    def _getFactory(self):
        return self.factory()

    #############################
    def _listeningEstablished(self, iListeningPort):
        self.curPort = iListeningPort.getHost().port
        self.iListeningPort = iListeningPort
        logger.info(" Port {} opened - listening".format(self.curPort))

    #############################
    def _listeningFailure(self, *args):
        logger.error("Listening on ports {} to {} failure".format(self.configDesc.startPort, self.configDesc.endPort))

#######################################################################################
class PendingConnectionsServer(GNRServer):
    #############################
    def __init__(self, configDesc, factory, sessionClass, useIp6=False):
        self.pendingConnections = {}
        self.connEstablishedForType = {}
        self.connFailureForType = {}
        self.sessionClass = sessionClass
        self._setConnEstablished()
        self._setConnFailure()
        GNRServer.__init__(self, configDesc, factory, useIp6)

    #############################
    def verifiedConn(self, connId):
        if connId in self.pendingConnections:
            del self.pendingConnections[connId]
        else:
            logger.error("Connection {} is unknown".format(connId))

    #############################
    def _addPendingRequest(self, type, taskOwner, port, keyId, args):
        hostInfos = self._getHostInfos(taskOwner, port, keyId)
        pc = PendingConnection(type, hostInfos, self.connEstablishedForType[type],
                               self.connFailureForType[type], args)
        self.pendingConnections[pc.id] = pc

    #############################
    def _syncPending(self):
        conns = [pen for pen in self.pendingConnections.itervalues() if pen.status in PendingConnection.connectStatuses]
        #TODO Zmiany dla innych statusow
        for conn in conns:
            if len(conn.hostInfos) == 0:
                conn.status = PenConnStatus.WaitingGlobal
                conn.failure(conn.id, *conn.args)
                #TODO Dalsze dzialanie w razie neipowodzenia
            else:
                conn.status = PenConnStatus.Waiting
                conn.lastTryTime = time.time()
                Network.connectToHost(conn.hostInfos, self.sessionClass, conn.established, conn.failure,
                                      conn.id, *conn.args)

    #############################
    def _getHostInfos(self, nodeInfo, port, keyId):
        return nodeInfoToHostInfos(nodeInfo, port)

    #############################
    def _setConnEstablished(self):
        pass

    #############################
    def _setConnFailure(self):
        pass

    #############################
    def _markConnected(self, connId, addr, port):
        hd = HostData(addr, port)
        pc = self.pendingConnections.get(connId)
        if pc is not None:
            pc.status = PenConnStatus.Connected
            try:
                idx = pc.hostInfos.index(hd)
                pc.hostInfos = pc.hostInfos[idx+1:]
            except ValueError:
                logger.warning("{}:{} not in connection hostinfos".format(addr, port))


#######################################################################################
class PenConnStatus:
    Inactive = 1
    Waiting = 2
    Connected = 3
    Failure = 4
    WaitingGlobal = 5

#######################################################################################
class PendingConnection:

    connectStatuses = [PenConnStatus.Inactive, PenConnStatus.Failure]

    #############################
    def __init__(self, type=None, hostInfos=None, established=None, failure=None, args=None):
        self.id = uuid.uuid4()
        self.hostInfos = hostInfos
        self.lastTryTime = time.time()
        self.established = established
        self.failure = failure
        self.args = args
        self.type = type
        self.status = PenConnStatus.Inactive

