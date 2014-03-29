from twisted.internet import reactor
from twisted.internet.protocol import Factory
from twisted.internet.endpoints import TCP4ServerEndpoint, TCP4ClientEndpoint, connectProtocol

from serverinterface import ServerInterface
from netconnstate import NetConnState
from peer import PeerSession
import time

class NetServerFactory( Factory ):
    #############################
    def __init__( self, p2pserver ):
        self.p2pserver = p2pserver

    #############################
    def buildProtocol( self, addr ):
        print "Protocol build for {}".format( addr )
        return NetConnState( self.p2pserver )

class P2PServer( ServerInterface ):
    #############################
    def __init__( self, hostAddress, clientVerssion, startPort, endPort, publicKey, seedHost, seedHostPort ):
        ServerInterface.__init__( self )

        self.clientVersion          = clientVerssion
        self.startPort              = startPort
        self.endPort                = endPort
        self.curPort                = self.startPort
        self.idealPeerCount         = 2
        self.peers                  = {}
        self.seedHost               = seedHost
        self.seedHostPort           = seedHostPort
        self.publicKey              = publicKey
        self.lastPeersRequest       = time.time()
        self.lastGetTasksRequest    = time.time()
        self.incommingPeers         = {}
        self.freePeers              = []
        self.taskServer             = None
        self.hostAddress            = hostAddress

        self.lastMessages           = []

        self.__startAccepting()

    #############################
    def setTaskServer( self, taskServer ):
        self.taskServer = taskServer

    #############################
    def syncNetwork( self ):
        self.__sendMessageGetPeers()

        if self.taskServer:
            self.__sendMessageGetTasks()

    #############################
    def newConnection( self, conn ):
        pp = conn.transport.getPeer()
        print "newConnection {} {}".format( pp.host, pp.port )
        peer = PeerSession( conn, self, pp.host, pp.port )
        conn.setPeerSession( peer )
        peer.start()
 
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
            if self.peers[ p ] == peerSession:
                del self.peers[ p ]
    
    #############################
    def setLastMessage( self, type, t, msg, address, port ):
        if len( self.lastMessages ) >= 5:
            self.lastMessages = self.lastMessages[ -4: ]

        self.lastMessages.append( [ type, t, address, port, msg ] )

    #############################
    def getLastMessages( self ):
        return self.lastMessages
                                    
    #############################
    def __startAccepting( self ):
        print "Enabling network accepting state"

        self.__runListenOnce()

        if self.seedHost and self.seedHostPort:
            if self.seedHost != "127.0.0.1" or self.seedHostPort != self.curPort: #FIXME workaround to test on one machine
                self.__connect( self.seedHost, self.seedHostPort )

    #############################   
    def __connect( self, address, port ):
        print "Connecting to host {} : {}".format( address ,port )
        endpoint = TCP4ClientEndpoint( reactor, address, port )
        connection = NetConnState( self );
        d = connectProtocol( endpoint, connection )
        d.addErrback( self.__connectionFailure )

    #############################
    def __sendMessageGetPeers( self ):
        while len( self.peers ) < self.idealPeerCount:
            if len( self.freePeers ) == 0:
                if time.time() - self.lastPeersRequest > 2:
                    self.lastPeersRequest = time.time()
                    for p in self.peers.values():
                        p.sendGetPeers()
                break

            x = int( time.time() ) % len( self.freePeers ) # get some random peer from freePeers
            self.incommingPeers[ self.freePeers[ x ] ][ "conn_trials" ] += 1 # increment connection trials
            self.__connect( self.incommingPeers[ self.freePeers[ x ] ][ "address" ], self.incommingPeers[ self.freePeers[ x ] ][ "port" ] )
            self.freePeers.remove( self.freePeers[ x ] )

    #############################
    def __sendMessageGetTasks( self ):
        if time.time() - self.lastGetTasksRequest > 2:
            self.lastGetTasksRequest = time.time()
            for p in self.peers.values():
                p.sendGetTasks()

    #############################
    def __connectionFailure( self, conn ):
        print "Connection to peer failure. {}".format( conn )

    #############################
    def __runListenOnce( self ):
        ep = TCP4ServerEndpoint( reactor, self.curPort )
        
        d = ep.listen( NetServerFactory( self ) )
        
        d.addCallback( self.__listeningEstablished )
        d.addErrback( self.__listeningFailure )

    #############################
    def __listeningEstablished( self, p ):
        assert p.getHost().port == self.curPort
        print "Port {} opened - listening".format( p.getHost().port )

    #############################
    #FIXME: tutaj trzeba zwiekszyc numer portu i odpalic ponownie endpoint listen - i tak az do momenty, kiedy sie uda lub skoncza sie porty - wtedy pad
    def __listeningFailure( self, p ):
        print "Opening {} port for listetning failed, trying the next one".format( self.curPort )

        self.curPort = self.curPort + 1

        if self.curPort <= self.endPort:
            self.__runListenOnce()
        else:
            #FIXME: some graceful terminations should take place here
            sys.exit( 0 )


