from message import MessageHello, MessagePing, MessagePong, MessageDisconnect, MessageGetPeers, MessagePeers, MessageGetTasks, MessageTasks
import time

class PeerSessionInterface:
    def __init__(self):
        pass

    def inretpret(self, msg):
        pass

class PeerSession(PeerSessionInterface):
    StateInitialize = 0
    StateConnecting = 1
    StateConnected  = 2 

    DCRBadProtocol      = "Bad protocol"
    DCRDuplicatePeers   = "Duplicate peers"

    def __init__(self, conn, server, address, port):
        PeerSessionInterface.__init__(self)
        self.server = server
        self.address = address
        self.id = 0
        self.port = port
        self.state = PeerSession.StateInitialize
        self.lastMessageTime = 0.0
        self.conn = conn
        self.lastDisconnectTime = None

    def __del__( self ):
        conn.close()

    def __str__(self):
        return "{} : {}".format(self.address, self.port)
     
    def start(self):
        print "Starting peer session {} : {}".format(self.address, self.port)
        self.sendHello()
        self.sendPing()        

    def disconnect(self, reason):
        print "Disconnecting {} : {} reason: {}".format( self.address, self.port, reason )
        if self.conn.isOpen():
            if self.lastDisconnectTime:
                self.dropped()
            else:
                self.sendDisconnect(reason)
                self.lastDisconnectTime = time.time()

    def dropped( self ):
        self.conn.close()
        self.server.removePeer( self )

    def ping(self, interval):
        if time.time() - self.lastMessageTime > interval:
            self.sendPing()

    def setConnecting(self):
        self.state = PeerSession.StateConnecting

    def setConnected(self):
        self.state = PeerSession.StateConnected

    def getState(self):
        return self.state

    def interpret(self, msg):
        self.lastMessageTime = time.time()

        if msg is None:
            self.disconnect( PeerSession.DCRBadProtocol )

        type = msg.getType()

        #localtime   = time.localtime()
        #timeString  = time.strftime("%H:%M:%S", localtime)
        #print "{} at {}".format( msg.serialize(), timeString )

        if type == MessagePing.Type:
            self.sendPong()
        elif type == MessagePong.Type:
            pass
        elif type == MessageDisconnect.Type:
            print "Disconnect reason: {}".format(msg.reason)
            print "Closing {} : {}".format( self.address, self.port )
            self.dropped()

        elif type == MessageHello.Type:
            self.port = msg.port
            self.id = msg.clientUID

            p = self.server.findPeer( self.id )

            if p and p != self and p.conn.isOpen():
                self.disconnect( PeerSession.DCRDuplicatePeers )

            self.server.peers[self.id] = self
            print "Add peer to client uid:{} address:{} port:{}".format(self.id, self.address, self.port)
            self.sendPing()

        elif type == MessageGetPeers.Type:
            self.sendPeers()

        elif type == MessagePeers.Type:
            peersInfo = msg.peersArray
            for pi in peersInfo:
                if pi[ "id" ] not in self.server.incommingPeers and pi[ "id" ] not in self.server.peers and pi[ "id" ] != self.server.publicKey:
                    print "add peer to incoming {} {} {}".format( pi[ "id" ], pi[ "address" ], pi[ "port" ] )
                    self.server.incommingPeers[ pi[ "id" ] ] = { "address" : pi[ "address" ], "port" : pi[ "port" ], "conn_trials" : 0 }
                    self.server.freePeers.append( pi[ "id" ] )
                    print self.server.incommingPeers

        elif type == MessageGetTasks.Type:
            tasks = self.server.taskServer.getTasksHeaders()
            self.sendTasks( tasks )

        elif type == MessageTasks.Type:
            for t in msg.tasksArray:
                if not self.server.taskServer.addTaskHeader( t ):
                    self.disconnect( PeerSession.DCRBadProtocol )

    # private
       
    def sendHello(self):
        self.send(MessageHello(self.server.curPort, self.server.publicKey))

    def sendPing(self):
        self.send(MessagePing())

    def sendPong(self):
        self.send(MessagePong())

    def sendDisconnect(self, reason):
        self.send( MessageDisconnect( reason ) )

    def sendGetPeers( self ):
        self.send( MessageGetPeers() )

    def sendGetTasks( self ):
        self.send( MessageGetTasks() )

    def sendPeers( self ):
        peersInfo = []
        for p in self.server.peers.values():
            peersInfo.append( { "address" : p.address, "port" : p.port, "id" : p.id } )
        self.send( MessagePeers( peersInfo ) )

    def sendTasks( self, tasks ):
        self.send( MessageTasks( tasks ) )

    def send(self, message):
        if not self.conn.sendMessage( message ):
            self.dropped()
            return
        self.lastMessageTime = time.time()