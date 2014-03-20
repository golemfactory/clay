from message import MessageHello, MessagePing, MessagePong, MessageDisconnect
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
        self.doWorkTask.start(0.1, False)
    
    def doWork(self):
        if time.time() - self.lastMessageTime >= self.client.pingInterval:
        self.sendPing()
        self.doWorkTask.start(0.1, False)
    
    def doWork(self):
        #pass
        if time.time() - self.lastMessageTime >= 1.0:
        self.sendPing()        

    def disconnect(self, reason):
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

        localtime   = time.localtime()
        timeString  = time.strftime("%H:%M:%S", localtime)
        print "{} at {} | ".format( msg.serialize(), timeString ),

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
                disconnect(DCRDuplicatePeers)

            self.server.peers[self.id] = self
            print "Add peer to client uid:{} address:{} port:{}".format(self.id, self.address, self.port)
            self.sendPing()

    # private
       
    def sendHello(self):
        self.send(MessageHello(self.client.listenPort, self.client.publicKey))
        self.send(MessageHello(self.server.port, self.server.publicKey))
        self.send(MessageHello(self.server.curPort, self.server.publicKey))

    def sendPing(self):
        self.send(MessagePing())

    def sendPong(self):
        self.send(MessagePong())

    def sendDisconnect(self, reason):
        self.send( MessageDisconnect( reason ) )

    def send(self, message):
        self.server.sendMessage(self.conn, message)
        self.lastMessageTime = time.time()
