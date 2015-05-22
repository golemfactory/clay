import time
import logging
import random

from golem.Message import MessageHello, MessagePing, MessagePong, MessageDisconnect, \
                          MessageGetPeers, MessagePeers, MessageGetTasks, MessageTasks, \
                          MessageRemoveTask, MessageGetResourcePeers, MessageResourcePeers, \
                          MessageDegree, MessageGossip, MessageStopGossip, MessageLocRank, MessageFindNode, \
                          MessageResendRandVal
from golem.network.p2p.NetConnState import NetConnState

logger = logging.getLogger(__name__)

class PeerSessionInterface:
    def __init__(self):
        pass

    def interpret(self, msg):
        pass

class PeerSession(PeerSessionInterface):

    ConnectionStateType = NetConnState

    StateInitialize = 0
    StateConnecting = 1
    StateConnected  = 2 

    DCRBadProtocol      = "Bad protocol"
    DCRDuplicatePeers   = "Duplicate peers"
    DCRTimeout          = "Timeout"
    DCRTooManyPeers     = "Too many peers"
    DCRRefresh          = "Refresh"
    DCROldMessage       = "Message expired"
    DCRWrongTimestamp   = "Wrong timestamp"
    DCRUnverified       = "Unverifed connection"

    ##########################
    def __init__( self, conn ):

        PeerSessionInterface.__init__(self)
        self.p2pService = None
        self.conn = conn
        pp = conn.transport.getPeer()
        self.address = pp.host
        self.id = 0
        self.clientKeyId = 0
        self.port = pp.port
        self.state = PeerSession.StateInitialize
        self.lastMessageTime = 0.0
        self.degree = 0
        self.messageTTL = 600
        self.futureTimeTolerance = 300
        self.randVal = random.random()
        self.verified = False
        self.canBeUnverified = [ MessageHello.Type, MessageResendRandVal.Type ]
        self.canBeUnsigned = [ MessageHello.Type ]
        self.canBeNotEncrypted = [ MessageHello.Type ]

        logger.info( "CREATING PEER SESSION {} {}".format( self.address, self.port ) )

        self.lastDisconnectTime = None

    ##########################
    def __str__(self):
        return "{} : {}".format(self.address, self.port)
     
    ##########################
    def start(self):
        logger.info( "Starting peer session {} : {}".format(self.address, self.port) )
        self.state = PeerSession.StateConnecting
        self.__sendHello()

    ##########################
    def dropped( self ):
        self.conn.close()
        self.p2pService.removePeer( self )

    ##########################
    def ping(self, interval):
        if time.time() - self.lastMessageTime > interval:
            self.__sendPing()

    ##########################
    def interpret(self, msg):
        self.lastMessageTime = time.time()

        #print "Receiving from {}:{}: {}".format( self.address, self.port, msg )

        if msg is None:
            self.disconnect( PeerSession.DCRBadProtocol )
            return

        if not hasattr(msg, "getType"):
            msg = self.p2pService.decrypt(msg)

        self.p2pService.setLastMessage( "<-", self.clientKeyId, time.localtime(), msg, self.address, self.port )

        type = msg.getType()
        if self.lastMessageTime - msg.timestamp > self.messageTTL:
            self.disconnect( PeerSession.DCROldMessage )
            return
        elif msg.timestamp - self.lastMessageTime > self.futureTimeTolerance:
            self.disconnect( PeerSession.DCRWrongTimestamp )
            return

        if not self.verified and type not in self.canBeUnverified:
            self.disconnect( PeerSession.DCRUnverified )
            return

        if not msg.encrypted and type not in self.canBeNotEncrypted:
            self.disconnect( PeerSession.DCRBadProtocol )
            return

        if (not type in self.canBeUnsigned) and (not self.p2pService.verifySig( msg.sig, msg.getShortHash(), self.clientKeyId ) ):
            logger.error( "Failed to verify message signature" )
            self.disconnect( PeerSession.DCRUnverified )
            return


        #localtime   = time.localtime()
       # timeString  = time.strftime("%H:%M:%S", localtime)
       # print "{} at {}".format( msg.serialize(), timeString )

        if type == MessagePing.Type:
            self.__sendPong()
        elif type == MessagePong.Type:
            self.p2pService.pongReceived( self.id, self.clientKeyId, self.address, self.port )
        elif type == MessageDisconnect.Type:
            logger.info( "Disconnect reason: {}".format(msg.reason) )
            logger.info( "Closing {} : {}".format( self.address, self.port ) )
            self.dropped()

        elif type == MessageHello.Type:
            self.port = msg.port
            self.id = msg.clientUID
            self.clientKeyId = msg.clientKeyId

            if not self.p2pService.verifySig( msg.sig, msg.getShortHash(), msg.clientKeyId ):
                logger.error( "Wrong signature for Hello msg" )
                self.disconnect( PeerSession.DCRUnverified )
                return


            enoughPeers = self.p2pService.enoughPeers()
            p = self.p2pService.findPeer( self.id )

            self.p2pService.addToPeerKeeper( self.id, self.clientKeyId, self.address, self.port )

            if enoughPeers:
                loggerMsg = "TOO MANY PEERS, DROPPING CONNECTION: {} {}: {}".format( self.id, self.address, self.port )
                logger.info(loggerMsg)
                nodesInfo = self.p2pService.findNode( self.p2pService.getKeyId() )
                self.__send( MessagePeers( nodesInfo ) )
                self.disconnect( PeerSession.DCRTooManyPeers )
                return

            if p and p != self and p.conn.isOpen():
#                self.__sendPing()
                loggerMsg = "PEER DUPLICATED: {} {} : {}".format( p.id, p.address, p.port )
                logger.warning( "{} AND {} : {}".format( loggerMsg, msg.clientUID, msg.port ) )
                self.disconnect( PeerSession.DCRDuplicatePeers )

            if not p:
                self.p2pService.addPeer( self.id, self )
                self.__sendHello()
                self.__send( MessageResendRandVal( msg.randVal ), sendUverified = True )


            #print "Add peer to client uid:{} address:{} port:{}".format(self.id, self.address, self.port)


        elif type == MessageGetPeers.Type:
            self.__sendPeers()

        elif type == MessagePeers.Type:
            peersInfo = msg.peersArray
            self.degree = len( peersInfo )
            for pi in peersInfo:
                self.p2pService.tryToAddPeer( pi )

        elif type == MessageGetTasks.Type:
            tasks = self.p2pService.getTasksHeaders()
            self.__sendTasks( tasks )

        elif type == MessageTasks.Type:
            for t in msg.tasksArray:
                if not self.p2pService.addTaskHeader( t ):
                    self.disconnect( PeerSession.DCRBadProtocol )

        elif type == MessageRemoveTask.Type:
            self.p2pService.removeTaskHeader( msg.taskId )

        elif type == MessageGetResourcePeers.Type:
            self.__sendResourcePeers()

        elif type == MessageResourcePeers.Type:
            self.p2pService.setResourcePeers( msg.resourcePeers )

        elif type == MessageDegree.Type:
            self.degree = msg.degree

        elif type == MessageGossip.Type:
            self.p2pService.hearGossip( msg.gossip )

        elif type == MessageStopGossip.Type:
            self.p2pService.stopGossip( self.id )

        elif type == MessageLocRank.Type:
            self.p2pService.safeNeighbourLocRank( self.id, msg.nodeId, msg.locRank )

        elif type == MessageFindNode.Type:
            nodesInfo = self.p2pService.findNode( msg.nodeKeyId )
            self.__send(MessagePeers( nodesInfo ))

        elif type == MessageResendRandVal.Type:
            if self.randVal == msg.randVal:
                self.verified = True
        else:
            self.disconnect( PeerSession.DCRBadProtocol )

    ##########################
    def sendGetPeers( self ):
        self.__send( MessageGetPeers() )

    ##########################
    def sendGetTasks( self ):
        self.__send( MessageGetTasks() )

    ##########################
    def sendRemoveTask( self, taskId ):
        self.__send( MessageRemoveTask( taskId ) )

    ##########################
    def sendGetResourcePeers( self ):
        self.__send( MessageGetResourcePeers() )

    ##########################
    def sendDegree(self, degree):
        self.__send( MessageDegree( degree ) )

    ##########################
    def sendGossip(self, gossip):
        self.__send( MessageGossip( gossip ) )

    ##########################
    def sendStopGossip(self):
        self.__send( MessageStopGossip())

    ##########################
    def sendLocRank( self, nodeId, locRank ):
        self.__send( MessageLocRank( nodeId, locRank ))

    ##########################
    def sendFindNode(self, nodeId ):
        self.__send( MessageFindNode( nodeId ) )

    ##########################
    def disconnect(self, reason):
        logger.info( "Disconnecting {} : {} reason: {}".format( self.address, self.port, reason ) )
        if self.conn.isOpen():
            if self.lastDisconnectTime:
                self.dropped()
            else:
                self.__sendDisconnect(reason)
                self.lastDisconnectTime = time.time()


    ##########################
    # PRIVATE SECTION
    ##########################
    def __sendHello(self):
        listenParams = self.p2pService.getListenParams()
        listenParams += (self.randVal, )
        self.__send( MessageHello( *listenParams ), sendUverified = True )

    ##########################
    def __sendPing(self):
        self.__send(MessagePing())

    ##########################
    def __sendPong(self):
        self.__send(MessagePong())

    ##########################
    def __sendDisconnect(self, reason):
        self.__send( MessageDisconnect( reason ) )

    ##########################
    def __sendPeers( self ):
        peersInfo = []
        for p in self.p2pService.peers.values():
            peersInfo.append( { "address" : p.address, "port" : p.port, "id" : p.id } )
        self.__send( MessagePeers( peersInfo ) )

    ##########################
    def __sendTasks( self, tasks ):
        self.__send( MessageTasks( tasks ) )

    ##########################
    def __sendResourcePeers( self ):
        resourcePeersInfo = self.p2pService.getResourcePeers()
        self.__send( MessageResourcePeers( resourcePeersInfo ) )

    ##########################
    def __send(self, message, sendUverified = False):
        if not self.verified and not sendUverified :
            logger.info("Connection hasn't been verified yet, not sending message")
            return
       # print "Sending to {}:{}: {}".format( self.address, self.port, message )
        if not self.conn.sendMessage( message ):
            self.dropped()
            return
        self.p2pService.setLastMessage( "->", self.clientKeyId, time.localtime(), message, self.address, self.port )

