from twisted.internet import reactor
from twisted.internet.protocol import Factory
from twisted.internet.endpoints import TCP4ServerEndpoint, TCP4ClientEndpoint, connectProtocol

from netconnstate import NetConnState
from computeconnstate import TaskConnState
from computesession import TaskSession
from peer import PeerSession
from task import TaskManager
import time

class NetServerFactory(Factory):
    #############################
    def __init__(self, p2pserver):
        self.p2pserver = p2pserver

    #############################
    def buildProtocol(self, addr):
        print "Protocol build for {}".format(addr)
        return NetConnState(self.p2pserver)


class P2PServerInterface:
    def __init__(self):
        pass

    def newConnection(self, connection):
        pass

class P2PServer(P2PServerInterface):
    #############################
    def __init__(self, clientVerssion, startPort, endPort, publicKey, seedHost, seedHostPort):
        P2PServerInterface.__init__(self)

        self.clientVersion      = clientVerssion
        self.startPort          = startPort
        self.endPort            = endPort
        self.curPort            = self.startPort
        self.idealPeerCount     = 2
        self.peers              = {}
        self.seedHost           = seedHost
        self.seedHostPort       = seedHostPort
        self.publicKey          = publicKey
        self.lastPeersRequest   = time.time()
        self.incommingPeers     = {}
        self.freePeers          = []

        self.__startAccepting()

    #############################
    def __startAccepting(self):
        print "Enabling network accepting state"

        self.__runListenOnceNet()

        if self.seedHost and self.seedHostPort:
            if self.seedHost != "127.0.0.1" or self.seedHostPort != self.netListeningPort: #FIXME workaround to test on one machine
                self.connectNet( self.seedHost, self.seedHostPort )

    #############################
    def newConnection(self, conn):
        pp = conn.transport.getPeer()
        print "newConnection {} {}".format(pp.host, pp.port)
        peer = PeerSession(conn, self, pp.host, pp.port)
        conn.setPeerSession(peer)
        peer.start()
     
    #############################   
    def connectNet(self, address, port):
        print "Connecting to host {} : {}".format(address ,port)
        endpoint = TCP4ClientEndpoint(reactor, address, port)
        connection = NetConnState(self);
        d = connectProtocol(endpoint, connection)
        d.addErrback(self.__connectionFailure)

    def isConnected( self, host, port ):
        if [ host, port ] in self.computeSessions:
            return self.computeSessions[ [ host, port ] ]
        else:
            return None

    #############################
    def pingPeers( self, interval ):
        for p in self.peers.values():
            p.ping( interval )

    #############################
    def findPeer( self, peerID ):
        if peerID in self.peers:
            return self.peers[ peerID ]
        else:
            return None

    #############################
    def removePeer( self, peerSession ):
        for p in self.peers.keys():
            if self.peers[p] == peerSession:
                del self.peers[p]

    #############################
    def removeComputeSession( self, computeSession ):
        self.computeSessions.remove( computeSession )

    #############################
    def sendMessageGetPeers( self ):
        while len( self.peers ) < self.idealPeerCount:
            if len( self.freePeers ) == 0:
                if time.time() - self.lastPeersRequest > 2:
                    self.lastPeersRequest = time.time()
                    for p in self.peers.values():
                        p.sendGetPeers()
                break

            x = int( time.time() ) % len( self.freePeers ) # get some random peer from freePeers
            self.incommingPeers[ self.freePeers[ x ] ][ "conn_trials" ] += 1 # increment connection trials
            self.connectNet( self.incommingPeers[ self.freePeers[ x ] ][ "address" ], self.incommingPeers[ self.freePeers[ x ] ][ "port" ] )
            self.freePeers.remove( self.freePeers[ x ] )

    #############################
    def sendMessageGetTasks( self ):
        if time.time() - self.lastGetTasksRequest > 2:
            self.lastGetTasksRequest = time.time()
            for p in self.peers.values():
                p.sendGetTasks()
            

    #############################
    def syncNetwork( self ):
        self.sendMessageGetPeers()
        self.taskManager.removeOldTasks()
        self.sendMessageGetTasks()

    #############################
    def __computeConnectionFailure(self, conn):
        p = conn.transport.getPeer()
        print "Cannot connect to {} {}".format( p.getHost(), p.getPort() )

    #############################
    def __connectionFailure( self, conn ):
        #assert isinstance(conn, ConnectionState)
        #p = conn.transport.getPeer()
        print "Connection to peer failure. {}".format( conn )



    #############################
    def __runListenOnceNet( self ):
        ep = TCP4ServerEndpoint( reactor, self.netListeningPort )
        
        d = ep.listen( NetServerFactory( self ) )
        
        d.addCallback( self.__netListeningEstablished )
        d.addErrback( self.__netListeningFailure )

    #############################
    def __netListeningEstablished(self, p):
        assert p.getHost().port == self.netListeningPort
        print "Port {} opened - listening".format(p.getHost().port)

    #############################
    #FIXME: tutaj trzeba zwiekszyc numer portu i odpalic ponownie endpoint listen - i tak az do momenty, kiedy sie uda lub skoncza sie porty - wtedy pad
    def __netListeningFailure(self, p):
        print "Opening {} port for listetning failed, trying the next one".format( self.netListeningPort )

        self.netListeningPort = self.netListeningPort + 1

        if self.netListeningPort <= self.endPort:
            self.__runListenOnceNet()
        else:
            #FIXME: some graceful terminations should take place here
            sys.exit(0)


