from NetConnState import NetConnState

from message import MessageHello, MessagePing, MessagePong, MessageDisconnect, MessageGetPeers, MessagePeers, MessageGetTasks, MessageTasks
import time

class PeerSessionInterface:
    def __init__(self):
        pass

    def inretpret(self, msg):
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

        #print "CREATING PEER SESSION {} {}".format( address, port )
        PeerSessionInterface.__init__(self)
        self.p2pService = None
        self.conn = conn
        pp = conn.transport.getPeer()
        self.address = pp.host
        self.id = 0
        self.port = pp.port
        self.state = PeerSession.StateInitialize
        self.lastMessageTime = 0.0

        self.lastDisconnectTime = None

    ##########################
    def __str__(self):
        return "{} : {}".format(self.address, self.port)
     
    ##########################
    def start(self):
        print "Starting peer session {} : {}".format(self.address, self.port)
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
            print "Disconnect reason: {}".format(msg.reason)
            print "Closing {} : {}".format( self.address, self.port )
            self.dropped()

        elif type == MessageHello.Type:
            self.port = msg.port
            self.id = msg.clientUID

            p = self.p2pService.findPeer( self.id )

            if p and p != self and p.conn.isOpen():
                self.__disconnect( PeerSession.DCRDuplicatePeers )

            if not p:
                self.__sendHello()
                self.p2pService.peers[self.id] = self

            #print "Add peer to client uid:{} address:{} port:{}".format(self.id, self.address, self.port)
            self.__sendPing()

        elif type == MessageGetPeers.Type:
            self.__sendPeers()

        elif type == MessagePeers.Type:
            peersInfo = msg.peersArray
            for pi in peersInfo:
                if pi[ "id" ] not in self.p2pService.incommingPeers and pi[ "id" ] not in self.p2pService.peers and pi[ "id" ] != self.p2pService.configDesc.clientUuid:
                    print "add peer to incoming {} {} {}".format( pi[ "id" ], pi[ "address" ], pi[ "port" ] )
                    self.p2pService.incommingPeers[ pi[ "id" ] ] = { "address" : pi[ "address" ], "port" : pi[ "port" ], "conn_trials" : 0 }
                    self.p2pService.freePeers.append( pi[ "id" ] )
                    print self.p2pService.incommingPeers

        elif type == MessageGetTasks.Type:
            tasks = self.p2pService.taskServer.getTasksHeaders()
            self.__sendTasks( tasks )

        elif type == MessageTasks.Type:
            for t in msg.tasksArray:
                if not self.p2pService.taskServer.addTaskHeader( t ):
                    self.__disconnect( PeerSession.DCRBadProtocol )

    ##########################
    def sendGetPeers( self ):
        self.__send( MessageGetPeers() )

    ##########################
    def sendGetTasks( self ):
        self.__send( MessageGetTasks() )

    ##########################
    # PRIVATE SECTION
       
    ##########################
    def __disconnect(self, reason):
        print "Disconnecting {} : {} reason: {}".format( self.address, self.port, reason )
        if self.conn.isOpen():
            if self.lastDisconnectTime:
                self.dropped()
            else:
                self.__sendDisconnect(reason)
                self.lastDisconnectTime = time.time()

    ##########################
    def __sendHello(self):
        self.__send(MessageHello(self.p2pService.p2pServer.curPort, self.p2pService.configDesc.clientUuid)) #FIXME: self.p2pService.configDesc.clientUuid (naprawde trzeba az tak???)

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
        self.lastMessageTime = time.time()
        self.p2pService.setLastMessage( "->", time.localtime(), message, self.address, self.port )

