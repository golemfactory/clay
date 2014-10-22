import time
import logging

from golem.Message import MessageHello, MessagePing, MessagePong, MessageDisconnect, \
                          MessageGetPeers, MessagePeers, MessageGetTasks, MessageTasks, \
                          MessageRemoveTask
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

    ##########################
    def __init__(self, conn ):

        PeerSessionInterface.__init__(self)
        self.p2pService = None
        self.conn = conn
        pp = conn.transport.getPeer()
        self.address = pp.host
        self.id = 0
        self.port = pp.port
        self.state = PeerSession.StateInitialize
        self.lastMessageTime = 0.0

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
        self.__sendPing()        

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
            self.__disconnect( PeerSession.DCRBadProtocol )
            return

        self.p2pService.setLastMessage( "<-", time.localtime(), msg, self.address, self.port )

        type = msg.getType()

        #localtime   = time.localtime()
        #timeString  = time.strftime("%H:%M:%S", localtime)
        #print "{} at {}".format( msg.serialize(), timeString )

        if type == MessagePing.Type:
            self.__sendPong()
        elif type == MessagePong.Type:
            pass
        elif type == MessageDisconnect.Type:
            logger.info( "Disconnect reason: {}".format(msg.reason) )
            logger.info( "Closing {} : {}".format( self.address, self.port ) )
            self.dropped()

        elif type == MessageHello.Type:
            self.port = msg.port
            self.id = msg.clientUID

            p = self.p2pService.findPeer( self.id )

            if p and p != self and p.conn.isOpen():
                loggerMsg = "PEER DUPLICATED: {} {} : {}".format( p.id, p.address, p.port )
                logger.warning( "{} AND {} : {}".format( loggerMsg, msg.clientUID, msg.port ) )
                self.__disconnect( PeerSession.DCRDuplicatePeers )

            if not p:
                self.__sendHello()
                self.p2pService.addPeer( self.id, self )

            #print "Add peer to client uid:{} address:{} port:{}".format(self.id, self.address, self.port)
            self.__sendPing()

        elif type == MessageGetPeers.Type:
            self.__sendPeers()

        elif type == MessagePeers.Type:
            peersInfo = msg.peersArray
            for pi in peersInfo:
                self.p2pService.tryToAddPeer( pi )

        elif type == MessageGetTasks.Type:
            tasks = self.p2pService.getTasksHeaders()
            self.__sendTasks( tasks )

        elif type == MessageTasks.Type:
            for t in msg.tasksArray:
                if not self.p2pService.addTaskHeader( t ):
                    self.__disconnect( PeerSession.DCRBadProtocol )

        elif type == MessageRemoveTask.Type:
            self.p2pService.removeTaskHeader( msg.taskId )

        else:
            self.__disconnect( PeerSession.DCRBadProtocol )

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
    # PRIVATE SECTION
       
    ##########################
    def __disconnect(self, reason):
        logger.info( "Disconnecting {} : {} reason: {}".format( self.address, self.port, reason ) )
        if self.conn.isOpen():
            if self.lastDisconnectTime:
                self.dropped()
            else:
                self.__sendDisconnect(reason)
                self.lastDisconnectTime = time.time()

    ##########################
    def __sendHello(self):
        listenParams = self.p2pService.getListenParams()
        self.__send( MessageHello( *listenParams ) )

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
    def __send(self, message):
        #print "Sending to {}:{}: {}".format( self.address, self.port, message )
        if not self.conn.sendMessage( message ):
            self.dropped()
            return
        self.p2pService.setLastMessage( "->", time.localtime(), message, self.address, self.port )

