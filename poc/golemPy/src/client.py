from twisted.internet.protocol import Factory
from twisted.internet import reactor
from twisted.internet.endpoints import TCP4ClientEndpoint, connectProtocol, TCP4ServerEndpoint
from twisted.protocols.amp import AMP
from p2pserver import P2PServer

import time
from protocol import GolemProtocol
from peer import PeerSession
import uuid

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
        self.publicKey = uuid.uuid1().get_hex()
        self.pingInterval =  PING_INTERVAL
        self.p2pserver = None

    def startNetwork(self):
        print "Starting network ..."
        self.p2pserver = P2PServer(1, self.listenPort)

    def connect(self, address, port):
        if self.p2pserver:
            self.p2pserver.connect(address, port)
        else:
            print "Trying to connect when server is not started yet"


