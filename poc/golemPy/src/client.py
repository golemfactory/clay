from twisted.internet.protocol import Factory
from twisted.internet import reactor
from twisted.internet.endpoints import TCP4ClientEndpoint, connectProtocol, TCP4ServerEndpoint
from twisted.protocols.amp import AMP

import time
from protocol import *
from peer import *
import uuid

class GolemServerFactory(Factory):

    def __init__(self, client):
        self.client = client

    def buildProtocol(self, addr):
        print "Protocol build"
        protocol = GolemProtocol(self.client)
        #self.client.newConnection(protocol)
        return protocol


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


PING_INTERVAL = 1.0

class Client:
    def __init__(self, port):
        self.listenPort = port
        self.lastPingTime = 0.0
        self.peers = {}
        self.ppMap = PeerToProtocol()
        self.publicKey = uuid.uuid1().get_hex()
        self.pingInterval =  PING_INTERVAL

    def doWork(self):
        if self.peer and time.time() - self.lastPingTime > 0.5:
            self.peer.sendMessage(PingMessage())

    def listeningEstablished(self, p):
        print "Listening established on {} : {}".format(p.getHost().host, p.getHost().port)

    def start(self):
        print "Start listening ..."
        endpoint = TCP4ServerEndpoint(reactor, self.listenPort)
        endpoint.listen(GolemServerFactory(self)).addCallback(self.listeningEstablished)

    def sendMessage(self, peer, message):
        protocol = self.ppMap.getProtocol(peer)
        assert protocol
        protocol.sendMessage(message)

    def newConnection(self, protocol):
        pp = protocol.transport.getPeer()
        peer = PeerSession(self, pp.host, pp.port)
        self.ppMap.add(peer, protocol)
        peer.start()

    def connectionFailure(self, p):
        assert isinstance(p, GolemProtocol)
        peer =  self.ppMap.getPeer[p]
        assert peer
        print "Connection to peer: {} failure.".format(peer)
        self.ppMap.remove(peer)

    def interpret(self, protocol, mess):
        peer = self.ppMap.getPeer(protocol)
        peer.interpret(mess)

    def connect(self, address, port):
        print "Connecting to host {} : {}".format(address ,port)
        endpoint = TCP4ClientEndpoint(reactor, address, port)
        protocol = GolemProtocol(self);
        d = connectProtocol(endpoint, protocol)
        d.addErrback(self.connectionFailure)
        return protocol


