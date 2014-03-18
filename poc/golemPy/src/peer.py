from message import *
from twisted.internet import task

class PeerSession:
    StateInitialize = 0
    StateConnecting = 1
    StateConnected  = 2 

    def __init__(self, client, address, port):

        self.client = client
        self.address = address
        self.id = 0
        self.port = port
        self.state = PeerSession.StateInitialize
        self.lastMessageTime = 0.0
        self.doWorkTask = task.LoopingCall(self.doWork)

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

        if type == PingMessage.Type:
            self.sendPong()
        elif type == PongMessage.Type:
            pass
        elif type == HelloMessage.Type:
            self.port = msg.port
            self.id = msg.clientUID
            self.client.peers[self.id] = self
#            print self.client.peers
            self.sendPing()

    # private
       
    def sendHello(self):
        self.send(HelloMessage(self.client.listenPort, self.client.publicKey))

    def sendPing(self):
        self.send(PingMessage())

    def sendPong(self):
        self.send(PongMessage())


    def send(self, message):
        self.client.sendMessage(self, message)
        self.lastMessageTime = time.time()