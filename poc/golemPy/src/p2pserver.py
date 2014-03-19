from connection import GolemConnection
from twisted.internet.endpoints import TCP4ServerEndpoint

class GolemServerFactory(Factory):

    def __init__(self, p2pserver):
        self.p2pserver = p2pserver

    def buildProtocol(self, addr):
        print "Protocol build for {}".format(addr)
        return GolemConnection(self.client)

class P2PServerInterface:
    def newConnection(self, connection):
        pass

class P2PServer(P2PServerInterface):
    def __init__(self, clientVerssion, port):
        P2PServerInterface.__init__(self)
        self.clientVersion = clientVerssion
        self.port = port
        self.idealPeerCount = 0
        self.peers = []

    def startAccepting(self):
        endpoint = TCP4ServerEndpoint(reactor, self.port)
        endpoint.listen(GolemServerFactory(self)).addCallback(self.listeningEstablished)

    def listeningEstablished(self, p):
        assert p.getHost().port == self.port
        print "Listening established on {} : {}".format(p.getHost().host, p.getHost().port)

    def setIdealPeerCount(self, n):
        self.idealPeerCount = n

    def newConnection(self, connection):
        pp = protocol.transport.getPeer()
        print "newConnection {} {}".format(pp.host, pp.port)
        peer = PeerSession(self, pp.host, pp.port)
        connection.setPeerSession(peer)
        self.peers.append(peer)
        peer.start()
        
    def connect(self, address, port):
        print "Connecting to host {} : {}".format(address ,port)
        endpoint = TCP4ClientEndpoint(reactor, address, port)
        connection = GolemConnection(self);
        d = connectProtocol(endpoint, connection)
        d.addErrback(self.connectionFailure)

    def connectionFailure(self, conn):
        assert isinstance(conn, GolemConnection)
        p = conn.transport.getPeer()
        print "Connection to peer: {} : {} failure.".format(p.host, p.port)

    def sendMessage(self, connection, msg):
        assert connection
        protocol.sendMessage(msg.serialize())
