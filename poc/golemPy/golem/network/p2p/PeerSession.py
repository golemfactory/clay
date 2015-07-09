import time
import logging
import random

from golem.Message import MessageHello, MessagePing, MessagePong, MessageDisconnect, \
                          MessageGetPeers, MessagePeers, MessageGetTasks, MessageTasks, \
                          MessageRemoveTask, MessageGetResourcePeers, MessageResourcePeers, \
                          MessageDegree, MessageGossip, MessageStopGossip, MessageLocRank, MessageFindNode, \
                          MessageRandVal, MessageWantToStartTaskSession, MessageSetTaskSession, \
                          MessageNatHole
from golem.network.p2p.NetConnState import NetConnState
from golem.network.p2p.Session import NetSession

logger = logging.getLogger(__name__)


class PeerSession(NetSession):

    ConnectionStateType = NetConnState

    StateInitialize = 0
    StateConnecting = 1
    StateConnected  = 2 

    DCRDuplicatePeers   = "Duplicate peers"
    DCRTooManyPeers     = "Too many peers"
    DCRRefresh          = "Refresh"

    ##########################
    def __init__(self, conn):

        NetSession.__init__(self, conn)
        self.p2pService = None
        self.id = 0
        self.state = PeerSession.StateInitialize
        self.degree = 0
        self.nodeId = None
        self.listenPort = None

        self.canBeUnverified.extend([ MessageHello.Type, MessageRandVal.Type ])
        self.canBeUnsigned.extend([ MessageHello.Type ])
        self.canBeNotEncrypted.extend([ MessageHello.Type ])

        logger.info("CREATING PEER SESSION {} {}".format(self.address, self.port))
        self.__setMsgInterprations()

    ##########################
    def __str__(self):
        return "{} : {}".format(self.address, self.port)
     
    ##########################
    def start(self):
        logger.info("Starting peer session {} : {}".format(self.address, self.port))
        self.state = PeerSession.StateConnecting
        self.__sendHello()

    ##########################
    def dropped(self):
        NetSession.dropped(self)
        self.p2pService.removePeer(self)

    ##########################
    def ping(self, interval):
        if time.time() - self.lastMessageTime > interval:
            self.__sendPing()

    ##########################
    def interpret(self, msg):
        self.p2pService.setLastMessage("<-", self.clientKeyId, time.localtime(), msg, self.address, self.port)
        NetSession.interpret(self, msg)

       # type = msg.getType()

        #localtime   = time.localtime()
       # timeString  = time.strftime("%H:%M:%S", localtime)
       # print "{} at {}".format(msg.serialize(), timeString)


    ##########################
    def sign(self, msg):
        if self.p2pService is None:
            logger.error("P2PService is None, can't sign a message.")
            return None

        msg.sign(self.p2pService)
        return msg

    ##########################
    def verify(self, msg):
        return self.p2pService.verifySig(msg.sig, msg.getShortHash(), self.clientKeyId)

    ##########################
    def encrypt(self, msg):
        return self.p2pService.encrypt(msg, self.clientKeyId)

    ##########################
    def decrypt(self, msg):
        if not self.p2pService:
            return msg

        try:
            msg = self.p2pService.decrypt(msg)
        except AssertionError:
            logger.warning("Failed to decrypt message, maybe it's not encrypted?")
        except Exception as err:
            logger.error("Failed to decrypt message {}".format(str(err)))
            assert False

        return msg

    ##########################
    def sendGetPeers(self):
        self._send(MessageGetPeers())

    ##########################
    def sendGetTasks(self):
        self._send(MessageGetTasks())

    ##########################
    def sendRemoveTask(self, taskId):
        self._send(MessageRemoveTask(taskId))

    ##########################
    def sendGetResourcePeers(self):
        self._send(MessageGetResourcePeers())

    ##########################
    def sendDegree(self, degree):
        self._send(MessageDegree(degree))

    ##########################
    def sendGossip(self, gossip):
        self._send(MessageGossip(gossip))

    ##########################
    def sendStopGossip(self):
        self._send(MessageStopGossip())

    ##########################
    def sendLocRank(self, nodeId, locRank):
        self._send(MessageLocRank(nodeId, locRank))

    ##########################
    def sendFindNode(self, nodeId):
        self._send(MessageFindNode(nodeId))

    ##########################
    def sendWantToStartTaskSession(self, nodeInfo, connId, superNodeInfo):
        self._send(MessageWantToStartTaskSession(nodeInfo, connId, superNodeInfo))

    ##########################
    def sendSetTaskSession(self, keyId, nodeInfo, connId, superNodeInfo):
        self._send(MessageSetTaskSession(keyId, nodeInfo, connId, superNodeInfo))

    ##########################
    def sendTaskNatHole(self, keyId, addr, port):
        self._send(MessageNatHole(keyId, addr, port))

    ##########################
    def _reactToPing(self, msg):
        self.__sendPong()

    ##########################
    def _reactToPong(self, msg):
        self.p2pService.pongReceived(self.id, self.clientKeyId, self.address, self.port)

    ##########################
    def _reactToHello(self, msg):
   #     self.port = msg.port
        self.id = msg.clientUID
        self.nodeInfo = msg.nodeInfo
        self.clientKeyId = msg.clientKeyId
        self.listenPort = msg.port

        if not self.verify(msg):
            logger.error("Wrong signature for Hello msg")
            self.disconnect(PeerSession.DCRUnverified)
            return

        enoughPeers = self.p2pService.enoughPeers()
        p = self.p2pService.findPeer(self.id)

        self.p2pService.addToPeerKeeper(self.id, self.clientKeyId, self.address, self.listenPort, self.nodeInfo)

        if enoughPeers:
            loggerMsg = "TOO MANY PEERS, DROPPING CONNECTION: {} {}: {}".format(self.id, self.address, self.port)
            logger.info(loggerMsg)
            nodesInfo = self.p2pService.findNode(self.p2pService.getKeyId())
            self._send(MessagePeers(nodesInfo))
            self.disconnect(PeerSession.DCRTooManyPeers)
            return

        if p and p != self and p.conn.isOpen():
        #   self._sendPing()
            loggerMsg = "PEER DUPLICATED: {} {} : {}".format(p.id, p.address, p.port)
            logger.warning("{} AND {} : {}".format(loggerMsg, msg.clientUID, msg.port))
            self.disconnect(PeerSession.DCRDuplicatePeers)

        if not p:
            self.p2pService.addPeer(self.id, self)
            self.__sendHello()
            self._send(MessageRandVal(msg.randVal), sendUnverified = True)

        #print "Add peer to client uid:{} address:{} port:{}".format(self.id, self.address, self.port)

    ##########################
    def _send(self, message, sendUnverified = False):
        NetSession._send(self, message, sendUnverified)
        self.p2pService.setLastMessage("->", self.clientKeyId, time.localtime(), message, self.address, self.port)


    ##########################
    def _reactToGetPeers(self, msg):
        self.__sendPeers()

    ##########################
    def _reactToPeers(self, msg):
        peersInfo = msg.peersArray
        self.degree = len(peersInfo)
        for pi in peersInfo:
            self.p2pService.tryToAddPeer(pi)

    ##########################
    def _reactToGetTasks(self, msg):
        tasks = self.p2pService.getTasksHeaders()
        self.__sendTasks(tasks)

    ##########################
    def _reactToTasks(self, msg):
        for t in msg.tasksArray:
            if not self.p2pService.addTaskHeader(t):
                self.disconnect(PeerSession.DCRBadProtocol)

    ##########################
    def _reactToRemoveTask(self, msg):
        self.p2pService.removeTaskHeader(msg.taskId)

    ##########################
    def _reactToGetResourcePeers(self, msg):
        self.__sendResourcePeers()

    ##########################
    def _reactToResourcePeers(self, msg):
        self.p2pService.setResourcePeers(msg.resourcePeers)

    ##########################
    def _reactToDegree(self, msg):
        self.degree = msg.degree

    ##########################
    def _reactToGossip(self, msg):
        self.p2pService.hearGossip(msg.gossip)

    ##########################
    def _reactToStopGossip(self, msg):
        self.p2pService.stopGossip(self.id)

    ##########################
    def _reactToLocRank(self, msg):
        self.p2pService.safeNeighbourLocRank(self.id, msg.nodeId, msg.locRank)

    ##########################
    def _reactToFindNode(self, msg):
        nodesInfo = self.p2pService.findNode(msg.nodeKeyId)
        self.__send(MessagePeers(nodesInfo))

    ##########################
    def _reactToRandVal(self, msg):
        if self.randVal == msg.randVal:
            self.verified = True
            self.p2pService.setSuggestedAddr(self.clientKeyId, self.address, self.port)

    ##########################
    def _reactToWantToStartTaskSession(self, msg):
        self.p2pService.peerWantTaskSession(msg.nodeInfo, msg.superNodeInfo)

    ##########################
    def _reactToSetTaskSession(self, msg):
        self.p2pService.peerWantToSetTaskSession(msg.keyId, msg.nodeInfo, msg.connId, msg.superNodeInfo)

    def _reactToNatHole(self, msg):
        self.p2pService.traverseNat(msg.keyId, msg.addr, msg.port)

    ##########################
    # PRIVATE SECTION
    ##########################
    def __sendHello(self):
        listenParams = self.p2pService.getListenParams()
        listenParams += (self.randVal,)
        self._send(MessageHello(*listenParams), sendUnverified = True)

    ##########################
    def __sendPing(self):
        self._send(MessagePing())

    ##########################
    def __sendPong(self):
        self._send(MessagePong())

    ##########################
    def __sendPeers(self):
        peersInfo = []
        for p in self.p2pService.peers.values():
            peersInfo.append({"address" : p.address, "port" : p.listenPort, "id" : p.id, "node": p.nodeInfo})
        self._send(MessagePeers(peersInfo))

    ##########################
    def __sendTasks(self, tasks):
        self._send(MessageTasks(tasks))

    ##########################
    def __sendResourcePeers(self):
        resourcePeersInfo = self.p2pService.getResourcePeers()
        self._send(MessageResourcePeers(resourcePeersInfo))

    ##########################
    def __setMsgInterprations(self):
        self.__setBasicMsgInterpretations()
        self.__setResourceMsgInterpretations()
        self.__setRankingMsgInterpretations()

    ##########################
    def __setBasicMsgInterpretations(self):
        self.interpretation.update({
            MessagePing.Type: self._reactToPing,
            MessagePong.Type: self._reactToPong,
            MessageHello.Type: self._reactToHello,
            MessageGetPeers.Type: self._reactToGetPeers,
            MessagePeers.Type: self._reactToPeers,
            MessageGetTasks.Type: self._reactToGetTasks,
            MessageTasks.Type: self._reactToTasks,
            MessageRemoveTask.Type: self._reactToRemoveTask,
            MessageFindNode.Type: self._reactToFindNode,
            MessageRandVal.Type: self._reactToRandVal,
            MessageWantToStartTaskSession.Type: self._reactToWantToStartTaskSession,
            MessageSetTaskSession.Type: self._reactToSetTaskSession,
            MessageNatHole.Type: self._reactToNatHole
       })

    ##########################
    def __setResourceMsgInterpretations(self):
        self.interpretation.update({
                                        MessageGetResourcePeers.Type: self._reactToGetResourcePeers,
                                        MessageResourcePeers.Type: self._reactToResourcePeers,
                                   })

    ##########################
    def __setRankingMsgInterpretations(self):
        self.interpretation.update({
                                        MessageDegree.Type: self._reactToDegree,
                                        MessageGossip.Type: self._reactToGossip,
                                        MessageLocRank.Type: self._reactToLocRank,
                                        MessageStopGossip.Type: self._reactToStopGossip,
                                   })



##############################################################################

class PeerSessionFactory:
    ##########################
    def getSession(self, connection):
        return PeerSession(connection)