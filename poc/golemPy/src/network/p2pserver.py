from twisted.internet import reactor
from twisted.internet.protocol import Factory
from twisted.internet.endpoints import TCP4ServerEndpoint, TCP4ClientEndpoint, connectProtocol

from netconnstate import NetConnState
from managerconnection import ManagerConnectionState
from managersession import ManagerSession
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

class P2PServer:
    #############################
    def __init__( self, hostAddress, configDesc ):

        self.configDesc             = configDesc

        self.curPort                = self.configDesc.startPort
        self.peers                  = {}
        self.clientUuid             = self.configDesc.clientUuid
        self.lastPeersRequest       = time.time()
        self.lastGetTasksRequest    = time.time()
        self.incommingPeers         = {}
        self.freePeers              = []
        self.taskServer             = None
        self.hostAddress            = hostAddress

        self.managerSession         = None

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
    def sendClientStateSnapshot( self, snapshot ):
        if self.managerSession:
            self.managerSession.sendClientStateSnapshot( snapshot )

        else:
            print "Cannot send snapshot !!! "

    #############################
    def newNMConnection( self, conn ):
        pp = conn.transport.getPeer()
        print "newNMConnection {} {}".format( pp.host, pp.port )
        self.managerSession = ManagerSession( conn, self, pp.host, pp.port )
        conn.setSession( self.managerSession )

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
    def managerSessionDisconnected( self, uid ):
        self.managerSession = None
                                   
    #############################
    def __startAccepting( self ):
        print "Enabling network accepting state"

        self.__runListenOnce()

        if self.configDesc.seedHost and self.configDesc.seedHostPort:
            if self.configDesc.seedHost != self.hostAddress or self.configDesc.seedHostPort != self.curPort: #FIXME workaround to test on one machine
                self.__connect( self.configDesc.seedHost, self.configDesc.seedHostPort )

        self.__connectNodesManager( "127.0.0.1", self.configDesc.managerPort )

    #############################   
    def __connectNodesManager( self, address, port ):
        print "Connecting to nodes manager host {} : {}".format( address ,port )
        endpoint = TCP4ClientEndpoint( reactor, address, port )
        connection = ManagerConnectionState( self );
        d = connectProtocol( endpoint, connection )
        d.addErrback( self.__connectionNMFailure )
        d.addCallback( self.__connectionNMEstablished )

    #############################   
    def __connect( self, address, port ):
        print "Connecting to host {} : {}".format( address ,port )
        endpoint = TCP4ClientEndpoint( reactor, address, port )
        connection = NetConnState( self );
        d = connectProtocol( endpoint, connection )
        d.addErrback( self.__connectionFailure )

    #############################
    def __sendMessageGetPeers( self ):
        while len( self.peers ) < self.configDesc.optNumPeers:
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
        print "Connection to peer failure. {}: {}".format( conn.transport.getPeer().host, conn.transport.getPeer().port )

    #############################
    def __connectionNMEstablished( self, conn ):
        if conn:
            pp = conn.transport.getPeer()
            print "__connectionNMEstablished {} {}".format( pp.host, pp.port )

    def __connectionNMFailure( self, conn ):
        print "Connection to nodes manager failure."

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
        print "Opening {} port for listening failed, trying the next one".format( self.curPort )

        self.curPort = self.curPort + 1

        if self.curPort <= self.configDesc.endPort:
            self.__runListenOnce()
        else:
            #FIXME: some graceful terminations should take place here
            sys.exit( 0 )


