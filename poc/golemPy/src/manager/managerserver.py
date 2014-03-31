from twisted.internet.protocol import Factory
from twisted.internet.endpoints import TCP4ServerEndpoint, TCP4ClientEndpoint, connectProtocol

from managerconnection import ManagerConnectionState
from managersession import ManagerSession

import pickle

class ManagerServerFactory(Factory):
    #############################
    def __init__( self, server ):
        self.server = server

    #############################
    def buildProtocol( self, addr ):
        print "Protocol build for {} : {}".format( addr.host, addr.port )
        cs = ManagerConnectionState( self.server )
        return cs

class ManagerServer:

    #############################
    def __init__( self, nodesManager, port, reactor = None ):
        self.port           = port
        self.managerSession = None
        self.reactor        = reactor
        self.nodesManager   = nodesManager

    #############################
    def setReactor( self, reactor ):
        self.reactor = reactor
        self.__startAccepting()

    #############################
    def __startAccepting( self ):
        self.__runListenOnce()

    #############################
    def __runListenOnce( self ):
        print self.reactor
        ep = TCP4ServerEndpoint( self.reactor, self.port )

        d = ep.listen( ManagerServerFactory( self ) )
        
        d.addCallback( self.__listeningEstablished )
        d.addErrback( self.__listeningFailure )

    #############################
    def __listeningEstablished( self, p ):
        assert p.getHost().port == self.port
        print "Manager server - port {} opened, listening".format( p.getHost().port )

    #############################
    def __listeningFailure(self, p):
        print "DUPA"
        print "Opening {} port for listening failed - bailign out".format( self.port )

    #############################
    def newNMConnection(self, conn):
        pp = conn.transport.getPeer()
        self.managerSession = ManagerSession( conn, self,  pp.host, pp.port )
        conn.setSession( self.managerSession )

    #############################
    def nodeStateSnapshotReceived( self, nss ):
        nssobj = pickle.loads( nss )
        self.nodesManager.appendStateUpdate( nssobj )
        
