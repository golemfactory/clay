from twisted.internet import reactor
from twisted.internet.protocol import Factory
from twisted.internet.endpoints import TCP4ServerEndpoint, TCP4ClientEndpoint, connectProtocol

from connection import GolemConnection
from peer import PeerSession

class GolemServerFactory(Factory):

    def __init__(self, p2pserver):
        self.p2pserver = p2pserver

    def buildProtocol(self, addr):
        print "Protocol build for {}".format(addr)
        return GolemConnection(self.p2pserver)

class P2PServerInterface:
    def __init__(self):
        pass

    def newConnection(self, connection):
        pass

class P2PServer(P2PServerInterface):
    def __init__(self, clientVerssion, startPort, endPort, publicKey, seedHost, seedHostPort):
        P2PServerInterface.__init__(self)
        self.clientVersion = clientVerssion
        self.startPort = startPort
        self.endPort = endPort
        self.curPort = self.startPort
        self.idealPeerCount = 0
        self.peers = {}
        self.seedHost = seedHost
        self.seedHostPort = seedHostPort
        self.startAccepting()
        self.publicKey = publicKey

    def startAccepting(self):
        print "Starting network service"

        self.__runListenOnce()

        if self.seedHost and self.seedHostPort:
            if self.seedHost != "127.0.0.1" or self.seedHostPort != self.curPort: #FIXME workaround to test on one machine
                self.connect( self.seedHost, self.seedHostPort )

    def setIdealPeerCount(self, n):
        self.idealPeerCount = n

    def newConnection(self, conn):
        pp = conn.transport.getPeer()
        print "newConnection {} {}".format(pp.host, pp.port)
        peer = PeerSession(conn, self, pp.host, pp.port)
        conn.setPeerSession(peer)
        peer.start()
        
    def connect(self, address, port):
        print "Connecting to host {} : {}".format(address ,port)
        endpoint = TCP4ClientEndpoint(reactor, address, port)
        connection = GolemConnection(self);
        d = connectProtocol(endpoint, connection)
        d.addErrback(self.__connectionFailure)

    def pingPeers( self, interval ):
        for p in self.peers.values():
            p.ping( interval )

    def sendMessage(self, conn, msg):
        assert conn
        conn.sendMessage(msg.serialize())

    def findPeer( self, peerID ):
        if peerID in self.peers:
            return self.peers[ peerID ]
        else:
            return None

    def removePeer( self, peerSession ):
        for p in self.peers.keys():
            if self.peers[p] == peerSession:
                del self.peers[p]

    def __connectionFailure(self, conn):
        assert isinstance(conn, GolemConnection)
        p = conn.transport.getPeer()
        print "Connection to peer: {} : {} failure.".format(p.host, p.port)

    def __runListenOnce( self ):
        ep = TCP4ServerEndpoint( reactor, self.curPort )
        
        d = ep.listen( GolemServerFactory( self ) )
        
        d.addCallback( self.__listeningEstablished )
        d.addErrback( self.__listeningFailure )

    def __listeningEstablished(self, p):
        assert p.getHost().port == self.curPort
        print "Listening established on {} : {}".format(p.getHost().host, p.getHost().port)

    #FIXME: tutaj trzeba zwiekszyc numer portu i odpalic ponownie endpoint listen - i tak az do momenty, kiedy sie uda lub skoncza sie porty - wtedy pad
    def __listeningFailure(self, p):
        print "Listetning on port {} failed, trying the next one".format( self.curPort )

        self.curPort = self.curPort + 1

        if self.curPort <= self.endPort:
            self.__runListenOnce()
        else:
            #FIXME: some graceful terminations should take place here
            sys.exit(0)

