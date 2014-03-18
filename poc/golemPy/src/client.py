from twisted.internet.protocol import Factory
from twisted.internet import reactor, task
from twisted.internet.endpoints import TCP4ClientEndpoint, connectProtocol, TCP4ServerEndpoint
from twisted.protocols.amp import AMP

import time
from protocol import *

class GolemServerFactory(Factory):

    def __init__(self, client):
        self.client = client

    def buildProtocol(self, addr):
        return GolemProtocol(self.client)

class Client:

    def __init__(self, port):
        self.listenPort = port
        self.lastPingTime = 0.0
        self.peer = None
        self.t = task.LoopingCall(self.doWork)
        self.t.start(0.5)

    def doWork(self):
        if self.peer and time.time() - self.lastPingTime > 0.5:
            self.peer.sendMessage(PingMessage())

    def start(self):
        print "Start listening ..."
        endpoint = TCP4ServerEndpoint(reactor, self.listenPort)
        endpoint.listen(GolemServerFactory(self))

    def connected(self, p):
        assert isinstance(p, GolemProtocol)
        self.peer = p
        p.sendMessage(HelloMessage())
        p.sendMessage(PingMessage())

    def interpret(self, p, mess):

        type = mess.getType()

        if type == PingMessage.Type:
            self.lastPingTime = time.time()
            return PongMessage()
        elif type == PongMessage.Type:
            pass
        elif type == HelloMessage.Type:
            return PingMessage()

        return None

    def connect(self, address, port):
        print "Connecting to host {} : {}".format(address ,port)
        endpoint = TCP4ClientEndpoint(reactor, address, port)
        endpoint.connect(Factory.forProtocol(AMP))
        d = connectProtocol(endpoint, GolemProtocol(self))
        d.addCallback(self.connected)


