from message import MessageHello, MessagePing, MessagePong
from twisted.internet import task
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

    def __init__(self, conn, server, address, port):
        PeerSessionInterface.__init__(self)
        self.server = server
        self.address = address
        self.id = 0
        self.port = port
        self.state = PeerSession.StateInitialize
        self.lastMessageTime = 0.0
        self.doWorkTask = task.LoopingCall(self.doWork)
        self.conn = conn

    def __str__(self):
        return "{} : {}".format(self.address, self.port)
     
    def start(self):
        print "Starting peer session {} : {}".format(self.address, self.port)
        self.sendHello()
        self.sendPing()
        self.doWorkTask.start(0.1, False)
    
    def doWork(self):
        #pass
        if time.time() - self.lastMessageTime >= 1.0:
            self.sendPing()

    def disconnect(self):
        pass
    
    def ping(self):
        pass
    
    def setConnecting(self):
        self.state = PeerSession.StateConnecting

    def setConnected(self):
        self.state = PeerSession.StateConnected

    def getState(self):
        return self.state

    def interpret(self, msg):
        self.lastMessageTime = time.time()

        type = msg.getType()

        localtime   = time.localtime()
        timeString  = time.strftime("%H:%M:%S", localtime)
        print "{} at {} | ".format( msg.serialize(), timeString ),

        if type == MessagePing.Type:
            self.sendPong()
        elif type == MessagePong.Type:
            pass
        elif type == MessageHello.Type:
            self.port = msg.port
            self.id = msg.clientUID
            self.server.peers[self.id] = self
            print "Add peer to client uid:{} address:{} port:{}".format(self.id, self.address, self.port)
            self.sendPing()

    # private
       
    def sendHello(self):
        self.send(MessageHello(self.server.curPort, self.server.publicKey))

    def sendPing(self):
        self.send(MessagePing())

    def sendPong(self):
        self.send(MessagePong())


    def send(self, message):
        self.server.sendMessage(self.conn, message)
        self.lastMessageTime = time.time()