import time
import logging
import random

from golem.network.transport.tcp_network import TCPNetwork, TCPConnectInfo, TCPAddress
from golem.network.p2p.peer_session import PeerSession
from golem.network.p2p.P2PServer import P2PServer
from PeerKeeper import PeerKeeper

logger = logging.getLogger(__name__)

class P2PService:
    ########################
    def __init__(self, node, configDesc, keysAuth, useIp6=False):

        self.configDesc             = configDesc

        self.peers                  = {}
        self.allPeers               = []
        self.clientUid              = self.configDesc.clientUid
        self.lastPeersRequest       = time.time()
        self.lastGetTasksRequest    = time.time()
        self.incommingPeers         = {}
        self.freePeers              = []
        self.taskServer             = None
        self.node                   = node
        self.lastMessageTimeThreshold = self.configDesc.p2pSessionTimeout
        self.refreshPeersTimeout    = 1200 #FIXME
        self.lastRefreshPeers       = time.time()

        self.lastMessages           = []

        self.resourcePort           = 0
        self.resourcePeers          = {}
        self.resourceServer         = None
        self.gossip                 = []
        self.stopGossipFromPeers    = set()
        self.neighbourLocRankBuff   = []

        self.keysAuth               = keysAuth
        self.peerKeeper             = PeerKeeper(keysAuth.get_key_id())
        self.suggestedAddrs         = {}

        self.connectionsToSet = {}
        self.p2pServer              = P2PServer(configDesc, self, useIp6)

        self.network = self.p2pServer.network

        self.connectToNetwork()

    #############################
    def connectToNetwork(self):
        self.p2pServer.start_accepting()
        if not self.wrongSeedData():
            self.__connect(self.configDesc.seedHost, self.configDesc.seedHostPort)

    #############################
    def wrongSeedData(self):
        try:
            if (int(self.configDesc.seedHostPort) < 1) or (int(self.configDesc.seedHostPort) > 65535):
                logger.warning(u"Seed port number out of range [1, 65535]: {}".format(self.configDesc.seedHostPort))
                return True
        except Exception, e:
            logger.error(u"Wrong seed port number {}: {}".format(self.configDesc.seedHostPort, str(e)))
            return True

        if len(self.configDesc.seedHost) <= 0 :
            return True
        return False

    #############################
    def setTaskServer(self, taskServer):
        self.taskServer = taskServer

    #############################
    def syncNetwork(self):

        self.__sendMessageGetPeers()

        if self.taskServer:
            self.__sendMessageGetTasks()

        self.__removeOldPeers()
        self.__syncPeerKeeper()

    #############################
    def __syncPeerKeeper(self):
        self.__removeSessionsToEndFromPeerKeeper()
        nodesToFind = self.peerKeeper.syncNetwork()
        self.__removeSessionsToEndFromPeerKeeper()
        if nodesToFind:
            self.sendFindNodes(nodesToFind)

    #############################
    def __removeSessionsToEndFromPeerKeeper(self):
        for peerId in self.peerKeeper.sessionsToEnd:
            self.removePeerById(peerId)
        self.peerKeeper.sessionsToEnd = []

    #############################
    def newSession(self, session):
        #session.p2pService = self
        self.allPeers.append(session)
        session.start()
 
    #############################
    def pingPeers(self, interval):
        for p in self.peers.values():
            p.ping(interval)
    
    #############################
    def findPeer(self, peerID):
        return self.peers.get(peerID)

    #############################
    def getPeers(self):
        return self.peers

    #############################
    def addPeer(self, id, peer):

        self.peers[id] = peer
        self.__sendDegree()

    #############################
    def addToPeerKeeper(self, id, peerKeyId, address, port, nodeInfo):
        peerToPingInfo = self.peerKeeper.addPeer(peerKeyId, id, address, port, nodeInfo)
        if peerToPingInfo and peerToPingInfo.nodeId in self.peers:
            peerToPing = self.peers[peerToPingInfo.nodeId]
            if peerToPing:
                peerToPing.ping(0)


    #############################
    def pongReceived(self, id, peerKeyId, address, port):
        self.peerKeeper.pongReceived(peerKeyId, id, address, port)

    #############################
    def tryToAddPeer(self, peerInfo):
        if self.__isNewPeer(peerInfo["id"]):
            logger.info("add peer to incoming {} {} {}".format(peerInfo["id"],
                                                             peerInfo["address"],
                                                             peerInfo["port"]))
            self.incommingPeers[peerInfo["id"]] = { "address" : peerInfo["address"],
                                                    "port" : peerInfo["port"],
                                                    "node": peerInfo["node"],
                                                    "conn_trials" : 0 }
            self.freePeers.append(peerInfo["id"])
            logger.debug(self.incommingPeers)


    #############################
    def removePeer(self, peerSession):

        if peerSession in self.allPeers:
            self.allPeers.remove(peerSession)

        for p in self.peers.keys():
            if self.peers[p] == peerSession:
                del self.peers[p]

        self.__sendDegree()

    #############################
    def removePeerById(self, peerId):
        peer = self.peers.get(peerId)
        if not peer:
            logger.info("Can't remove peer {}, unknown peer".format(peerId))
            return
        if peer in self.allPeers:
            self.allPeers.remove(peer)
        del self.peers[peerId]

        self.__sendDegree()

    #############################
    def enoughPeers(self):
        return len(self.peers) >= self.configDesc.optNumPeers

    #############################
    def setLastMessage(self, type, clientKeyId, t, msg, address, port):
        self.peerKeeper.setLastMessageTime(clientKeyId)
        if len(self.lastMessages) >= 5:
            self.lastMessages = self.lastMessages[-4:]

        self.lastMessages.append([type, t, address, port, msg])

    #############################
    def getLastMessages(self):
        return self.lastMessages
    
    ############################# 
    def managerSessionDisconnect(self, uid):
        self.managerSession = None

    #############################
    def change_config(self, configDesc):
        self.configDesc = configDesc
        self.p2pServer.change_config(configDesc)

        self.lastMessageTimeThreshold = self.configDesc.p2pSessionTimeout

        for peer in self.peers.values():
            if (peer.port == self.configDesc.seedHostPort) and (peer.address == self.configDesc.seedHostPort):
                return

        if not self.wrongSeedData():
            self.__connect(self.configDesc.seedHost, self.configDesc.seedHostPort)

        if self.resourceServer:
            self.resourceServer.change_config(configDesc)

    #############################
    def changeAddress(self, thDictRepr):
        try:
            id = thDictRepr["clientId"]

            if self.peers[id]:
                thDictRepr ["address"] = self.peers[id].address
                thDictRepr ["port"] = self.peers[id].port
        except Exception, err:
            logger.error("Wrong task representation: {}".format(str(err)))

    ############################
    def getListenParams(self):
        return (self.p2pServer.cur_port, self.configDesc.clientUid, self.keysAuth.get_key_id(), self.node)

    ############################
    def getPeersDegree(self):
        return  { peer.id: peer.degree for peer in self.peers.values() }

    #############################
    def get_key_id(self):
        return self.peerKeeper.peerKeyId

    #############################
    def encrypt(self, message, publicKey):
        if publicKey == 0:
            return message
        return self.keysAuth.encrypt(message, publicKey)

    #############################
    def decrypt(self, message):
        return self.keysAuth.decrypt(message)

    #############################
    def sign(self, data):
        return self.keysAuth.sign(data)

    #############################
    def verifySig(self, sig, data, publicKey):
        return self.keysAuth.verify(sig, data, publicKey)

    def setSuggestedAddr(self, clientKeyId, addr, port):
        self.suggestedAddrs[clientKeyId] = addr

    #Kademlia functions
    #############################
    def sendFindNodes(self, nodesToFind):
        for nodeKeyId, neighbours in nodesToFind.iteritems():
            for neighbour in neighbours:
                peer =  self.peers.get(neighbour.nodeId)
                if peer:
                    peer.send_find_node(nodeKeyId)

    #Find node
    #############################
    def findNode(self, nodeKeyId):
        neighbours = self.peerKeeper.neighbours(nodeKeyId)
        nodesInfo = []
        for n in neighbours:
            nodesInfo.append({ "address": n.ip, "port": n.port, "id": n.nodeId, "node": n.nodeInfo})
        return nodesInfo


    #Resource functions
    #############################
    def setResourceServer (self, resourceServer):
        self.resourceServer = resourceServer

    ############################
    def setResourcePeer(self, addr, port):
        self.resourcePort = port
        self.resourcePeers[self.clientUid] = [addr, port, self.keysAuth.get_key_id(), self.node]

    #############################
    def sendGetResourcePeers(self):
        for p in self.peers.values():
            p.send_get_resource_peers()

    ############################
    def getResourcePeers(self):
        resourcePeersInfo = []
        for clientId, [addr, port, keyId, nodeInfo] in self.resourcePeers.iteritems():
            resourcePeersInfo.append({ 'clientId': clientId, 'addr': addr, 'port': port, 'keyId': keyId,
                                       'node': nodeInfo })

        return resourcePeersInfo

    ############################
    def setResourcePeers(self, resourcePeers):
        print "P2P SET RESOURCE PEERS {}".format(resourcePeers)
        for peer in resourcePeers:
            try:
                if peer['clientId'] != self.clientUid:
                    self.resourcePeers[peer['clientId']]  = [peer['addr'], peer['port'], peer['keyId'], peer['node']]
            except Exception, err:
                logger.error("Wrong set peer message (peer: {}): {}".format(peer, str(err)))
        resourcePeersCopy = self.resourcePeers.copy()
        if self.clientUid in resourcePeersCopy:
            del resourcePeersCopy[self.clientUid]
        self.resourceServer.setResourcePeers(resourcePeersCopy)

    #############################
    def sendPutResource(self, resource, addr, port, copies):

        if len (self.peers) > 0:
            p = self.peers.itervalues().next()
            p.sendPutResource(resource, addr, port, copies)

    #############################
    def putResource(self, resource, addr, port, copies):
        self.resourceServer.putResource(resource, addr, port, copies)

    #TASK FUNCTIONS
    ############################
    def getTasksHeaders(self):
        return self.taskServer.getTasksHeaders()

    ############################
    def addTaskHeader(self, thDictRepr):
        return self.taskServer.addTaskHeader(thDictRepr)

    ############################
    def removeTaskHeader(self, taskId):
        return self.taskServer.removeTaskHeader(taskId)

    ############################
    def removeTask(self, taskId):
        for p in self.peers.values():
            p.send_remove_task(taskId)

    ############################
    def wantToStartTaskSession(self, keyId, nodeInfo, connId, superNodeInfo=None):
        logger.debug("Try to start task sesion {}".format(keyId))
        msgSnd = False
        for peer in self.peers.itervalues():
            if peer.key_id == keyId:
                peer.send_want_to_start_task_session(nodeInfo, connId, superNodeInfo)
                return

        for peer in self.peers.itervalues():
            if peer.key_id != nodeInfo.key:
                peer.send_set_task_session(keyId, nodeInfo, connId, superNodeInfo)
                msgSnd = True

        #TODO Tylko do wierzcholkow blizej supernode'ow / blizszych / lepszych wzgledem topologii sieci

        if not msgSnd and nodeInfo.key == self.get_key_id():
            self.taskServer.final_conn_failure(connId)

    ############################
    def informAboutTaskNatHole(self, keyId, rvKeyId, addr, port, ansConnId):
        logger.debug("Nat hole ready {}:{}".format(addr,port))
        for peer in self.peers.itervalues():
            if peer.key_id == keyId:
                peer.send_task_nat_hole(rvKeyId, addr, port, ansConnId)
                return

    ############################
    def traverseNat(self, keyId, addr, port, connId, superKeyId):
        self.taskServer.traverseNat(keyId, addr, port, connId, superKeyId)

    ############################
    def informAboutNatTraverseFailure(self, keyId, resKeyId, connId):
        for peer in self.peers.itervalues():
            if peer.key_id == keyId:
                peer.send_inform_about_nat_traverse_failure(resKeyId, connId)
        #TODO CO jak juz nie ma polaczenia?

    ############################
    def sendNatTraverseFailure(self, keyId, connId):
        for peer in self.peers.itervalues():
            if peer.key_id == keyId:
                peer.send_nat_traverse_failure(connId)
        #TODO Co jak nie ma tego polaczenia

    ############################
    def traverseNatFailure(self, connId):
        self.taskServer.traverseNatFailure(connId)

    ############################
    def peerWantTaskSession(self, nodeInfo, superNodeInfo, connId):
        #TODO Reakcja powinna nastapic tylko na pierwszy taki komunikat
        self.taskServer.startTaskSession(nodeInfo, superNodeInfo, connId)

    ############################
    def peerWantToSetTaskSession(self, keyId, nodeInfo, connId, superNodeInfo):
        logger.debug("Peer want to set task session with {}".format(keyId))
        if connId in self.connectionsToSet:
            return

        #TODO Lepszy mechanizm wyznaczania supernode'a
        if superNodeInfo is None and self.node.isSuperNode():
            superNodeInfo = self.node

        #TODO Te informacje powinny wygasac (byc usuwane po jakims czasie)
        self.connectionsToSet[connId] = (keyId, nodeInfo, time.time())
        self.wantToStartTaskSession(keyId, nodeInfo, connId, superNodeInfo)

    #############################
    #RANKING FUNCTIONS          #
    #############################
    def sendGossip(self, gossip, sendTo):
        for peerId in sendTo:
            peer = self.findPeer(peerId)
            if peer is not None:
                peer.send_gossip(gossip)

    #############################
    def hearGossip(self, gossip):
        self.gossip.append(gossip)

    #############################
    def popGossip(self):
        gossip = self.gossip
        self.gossip = []
        return gossip

    #############################
    def sendStopGossip(self):
        for peer in self.peers.values():
            peer.send_stop_gossip()

    #############################
    def stopGossip(self, id):
        self.stopGossipFromPeers.add(id)

    #############################
    def popStopGossipFromPeers(self):
        stop = self.stopGossipFromPeers
        self.stopGossipFromPeers = set()
        return stop

    #############################
    def pushLocalRank(self, nodeId, locRank):
        for peer in self.peers.values():
            peer.send_loc_rank(nodeId, locRank)

    #############################
    def safeNeighbourLocRank(self, neighId, aboutId, rank):
        self.neighbourLocRankBuff.append([neighId, aboutId, rank])

    #############################
    def popNeighboursLocRanks(self):
        nrb = self.neighbourLocRankBuff
        self.neighbourLocRankBuff = []
        return nrb

    new_connection = newSession

    #############################
    #PRIVATE SECTION
    #############################
    def __connect(self, address, port):
        connect_info = TCPConnectInfo([TCPAddress(address, port)], self.__connectionEstablished, self.__connectionFailure)
        self.network.connect(connect_info)
        #self.network.connect(address, port, self.__connectionEstablished, self.__connectionFailure)

    #############################
    def __connectToHost(self, peer):
        addr = self.suggestedAddrs.get(peer['node'].key)
        tcp_addresses = P2PService.__node_info_to_tcp_addresses(peer['node'], peer['port'])
        if addr:
            tcp_addresses = [TCPAddress(addr, peer['port'])] + tcp_addresses
        connect_info = TCPConnectInfo(tcp_addresses, self.__connectionEstablished, self.__connectionFailure)
        self.network.connect(connect_info)

    # Tmp function: to be remove
    @staticmethod
    def __node_info_to_tcp_addresses(nodeInfo, port):
        tcp_addresses = [TCPAddress(i, port) for i in nodeInfo.prvAddresses]
        if nodeInfo.pubPort:
            tcp_addresses.append(TCPAddress(nodeInfo.pubAddr, nodeInfo.pubPort))
        else:
            tcp_addresses.append(TCPAddress(nodeInfo.pubAddr, port))
        return tcp_addresses


    #############################
    def __sendMessageGetPeers(self):
        while len(self.peers) < self.configDesc.optNumPeers:
            if len(self.freePeers) == 0:
                peer = None #FIXME
#                peer = self.peerKeeper.getRandomKnownNode()
                if not peer or peer.nodeId in self.peers:
                    if time.time() - self.lastPeersRequest > 2:
                        self.lastPeersRequest = time.time()
                        for p in self.peers.values():
                            p.send_get_peers()
                else:
                    self.tryToAddPeer({"id": peer.nodeId, "address": peer.ip, "port": peer.port, "node": peer.nodeInfo })
                break

            x = int(time.time()) % len(self.freePeers) # get some random peer from freePeers
            peer = self.freePeers[x]
            self.incommingPeers[self.freePeers[x]]["conn_trials"] += 1 # increment connection trials
            logger.info("Connecting to peer {}".format(peer))
            # self.__connect(self.incommingPeers[peer]["address"], self.incommingPeers[peer]["port"])
            self.__connectToHost(self.incommingPeers[peer])
            self.freePeers.remove(peer)

    #############################
    def __sendMessageGetTasks(self):
        if time.time() - self.lastGetTasksRequest > 2:
            self.lastGetTasksRequest = time.time()
            for p in self.peers.values():
                p.send_get_tasks()

    #############################
    def __connectionEstablished(self, session):
#        session.p2pService = self
        self.allPeers.append(session)

        logger.debug("Connection to peer established. {}: {}".format(session.conn.transport.getPeer().host, session.conn.transport.getPeer().port))

    #############################
    def __connectionFailure(self):
        logger.error("Connection to peer failure.")

    #############################
    def __isNewPeer (self, id):
        if id in self.incommingPeers or id in self.peers or id == self.configDesc.clientUid:
            return False
        else:
            return True

    #############################
    def __removeOldPeers(self):
        curTime = time.time()
        for peerId in self.peers.keys():
            if curTime - self.peers[peerId].last_message_time > self.lastMessageTimeThreshold:
                self.peers[peerId].disconnect(PeerSession.DCRTimeout)

        if curTime - self.lastRefreshPeers > self.refreshPeersTimeout:
            self.lastRefreshPeers = time.time()
            if len(self.peers) > 1:
                peerId = random.choice(self.peers.keys())
                self.peers[peerId].disconnect(PeerSession.DCRRefresh)


    #############################
    def __sendDegree(self):
        degree = len(self.peers)
        for p in self.peers.values():
            p.send_degree(degree)