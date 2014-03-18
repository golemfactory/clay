from twisted.internet.protocol import Factory
from twisted.internet import reactor, task
from twisted.internet.endpoints import TCP4ClientEndpoint, connectProtocol, TCP4ServerEndpoint
from twisted.protocols.amp import AMP

import time
from protocol import *
from peer import *

class GolemServerFactory(Factory):

    def __init__(self, client):
        self.client = client

    def buildProtocol(self, addr):
        return GolemProtocol(self.client)


class PeerToProtocol:
    def __init__(self):
        self.peerToProtocol = {}
        self.protocolToPeer = {}

    def getPeer(self, protocol):
        return self.protocolToPeer[protocol]

    def getProtocol(self, peer):
        return self.peerToProtocol[peer]

    def add(self, peer, protocol):
        self.peerToProtocol[peer] = protocol
        self.protocolToPeer[protocol] = peer

    def remove(peer):
        protocol = self.peerToProtocol[peer]
        del self.peerToProtocol[peer]
        del self.protocolToPeer[protocol]

    def remove(protocol):
        peer = self.protocolToPeer[protocol]
        del self.protocolToPeer[protocol]
        del self.peerToProtocol[peer]


class Client:

    def __init__(self, port):
        self.listenPort = port
        self.lastPingTime = 0.0
        self.peer = None
        self.t = task.LoopingCall(self.doWork)
        self.t.start(0.5)
        self.peers = []
        self.ppMap = PeerToProtocol()

    def doWork(self):
        if self.peer and time.time() - self.lastPingTime > 0.5:
            self.peer.sendMessage(PingMessage())

    def start(self):
        print "Start listening ..."
        endpoint = TCP4ServerEndpoint(reactor, self.listenPort)
        endpoint.listen(GolemServerFactory(self))

    def connectToPeer(self, peer):
        peer.setConnecting()
        protocol = connect(self, peer.address, peer.port)
        self.peers.append(peer)
        self.ppMap.add(peer, protocol)
        

    def sendMessage(self, peer, message):
        protocol = self.ppMap.getProtocol(peer)
        assert protocol
        protocol.sendMessage(message)

    def connected(self, p):
        assert isinstance(p, GolemProtocol)
        peer =  self.ppMap.getPeer[p]
        assert peer
        peer.setConnected()

    def connectionFailure(self, p):
        assert isinstance(p, GolemProtocol)
        peer =  self.ppMap.getPeer[p]
        assert peer
        print "Connectio nto peer: {} failure.".format(peer)
        self.ppMap.remove(peer)

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
        protocol = GolemProtocol(self);
        d = connectProtocol(endpoint, protocol)
        d.addCallback(self.connected)
        d.addErrback(self.connectionFailure)
        return protocol


