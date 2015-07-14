import logging
import time
import uuid

from collections import deque
from stun import FullCone, OpenInternet

from golem.network.transport.Tcp import Network, HostData, nodeInfoToHostInfos

logger = logging.getLogger(__name__)

#######################################################################################
class GNRServer:
    #############################
    def __init__(self, configDesc, protocolFactory, sessionFactory, useIp6=False):
        self.configDesc = configDesc
        self.protocolFactory = protocolFactory
        self.sessionFactory = sessionFactory

        self.curPort = 0
        self.useIp6 = useIp6
        self.iListeningPort = None

        self.network = Network(protocolFactory, sessionFactory, useIp6)

    #############################
    def setProtocolFactory(self, protocolFactory):
        self.network.protocolFactory = protocolFactory

    #############################
    def setSessionFactory(self, sessionFactory):
        self.network.sessionFactory = sessionFactory

    #############################
    def newConnection(self, session):
        pass

    #############################
    def changeConfig(self, configDesc):
        self.configDesc = configDesc

        if self.iListeningPort is None:
            self.startAccepting()
            return

        if self.iListeningPort and (configDesc.startPort > self.curPort or configDesc.endPort < self.curPort):
            self.iListeningPort.stopListening()
            self.startAccepting()

    #############################
    def startAccepting(self):
        logger.info("Enabling network accepting state")

        self.network.listen(self.configDesc.startPort, self.configDesc.endPort, self._listeningEstablished,
                            self._listeningFailure)

    #############################
    def _listenOnPort(self, port, listeningEstablished, listeningFailure, extraData):
        self.network.listen(port, port, listeningEstablished, listeningFailure, *extraData)


    #############################
    def _listeningEstablished(self, iListeningPort, *args):
        self.curPort = iListeningPort.getHost().port
        self.iListeningPort = iListeningPort
        logger.info(" Port {} opened - listening".format(self.curPort))

    #############################
    def _listeningFailure(self, *args):
        logger.error("Listening on ports {} to {} failure".format(self.configDesc.startPort, self.configDesc.endPort))

#######################################################################################
class PendingConnectionsServer(GNRServer):

    supportedNatTypes = [FullCone, OpenInternet]

    #############################
    def __init__(self, configDesc, protocolFactory, sessionFactory, useIp6=False):
        self.pendingConnections = {}
        self.connEstablishedForType = {}
        self.connFailureForType = {}
        self.connFinalFailureForType = {}
        self._setConnEstablished()
        self._setConnFailure()
        self._setConnFinalFailure()

        self.pendingListenings = deque([])
        self.openListenings = {}
        self.listenWaitTime = 1
        self.listenEstablishedForType = {}
        self.listenFailureForType = {}
        self._setListenEstablished()
        self._setListenFailure()
        self.lastCheckListeningTime = time.time()
        self.listeningRefreshTime = 120
        self.listenPortTTL = 3600

        GNRServer.__init__(self, configDesc, protocolFactory, sessionFactory, useIp6)

    #############################
    def verifiedConn(self, connId):
        if connId in self.pendingConnections:
            del self.pendingConnections[connId]
        else:
            logger.error("Connection {} is unknown".format(connId))

    #############################
    def finalConnFailure(self, connId):
        conn = self.pendingConnections.get(connId)
        if conn:
            self.connFinalFailureForType[conn.type](connId, *conn.args)
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
    def _addPendingListening(self, type, port, args):
        pl = PendingListening(type, port, self.listenEstablishedForType[type],
                              self.listenFailureForType[type], args)
        pl.args = (pl.id, ) + pl.args
        self.pendingListenings.append(pl)

    #############################
    def _syncPending(self):
        cntTime = time.time()
        while len(self.pendingListenings) > 0:
            if cntTime - self.pendingListenings[0].time < self.listenWaitTime:
                break
            pl = self.pendingListenings.popleft()
            self._listenOnPort(pl.port, pl.established, pl.failure, pl.args)
            self.openListenings[pl.id] = pl #TODO Powinny umierac jesli zbyt dlugo sa aktywne

        conns = [pen for pen in self.pendingConnections.itervalues() if pen.status in PendingConnection.connectStatuses]
        #TODO Zmiany dla innych statusow
        for conn in conns:
            if len(conn.hostInfos) == 0:
                conn.status = PenConnStatus.WaitingAlt
                conn.failure(conn.id, *conn.args)
                #TODO Dalsze dzialanie w razie neipowodzenia
            else:
                conn.status = PenConnStatus.Waiting
                conn.lastTryTime = time.time()
                self.network.connectToHost(conn.hostInfos, conn.established, conn.failure, conn.id, *conn.args)

    #############################
    def _removeOldListenings(self):
        cntTime = time.time()
        if cntTime - self.lastCheckListeningTime > self.listeningRefreshTime:
            self.lastCheckListeningTime = time.time()
            listeningsToRemove = []
            for olId, listening in self.openListenings.iteritems():
                if cntTime - listening.time > self.listenPortTTL:
                    if listening.listenPort:
                       listening.listenPort.stopListening()
                    listeningsToRemove.append(olId)
            for olId in listeningsToRemove:
                del self.openListenings[olId]

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
    def _setConnFinalFailure(self):
        pass

    #############################
    def _setListenEstablished(self):
        pass

    #############################
    def _setListenFailure(self):
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
    WaitingAlt = 5

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

class PendingListening:

    #############################
    def __init__(self, type=None, port=None, established=None, failure=None, args=None):
        self.id = uuid.uuid4()
        self.time = time.time()
        self.established = established
        self.failure = failure
        self.args = args
        self.port = port
        self.type = type
        self.tries = 0
        self.listeningPort = None