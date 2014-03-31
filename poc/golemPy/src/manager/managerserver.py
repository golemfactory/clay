from twisted.internet.protocol import Factory
from twisted.internet.endpoints import TCP4ServerEndpoint, TCP4ClientEndpoint, connectProtocol

from managerconnection import ManagerConnectionState
from managersession import ManagerSession


class ManagerServerFactory(Factory):
    #############################
    def __init__( self, server ):
        self.server = server

    #############################
    def buildProtocol( self, addr ):
        print "Protocol build for {}".format(addr)
        return ManagerConnectionState( self.server )

class ManagerServer:

    #############################
    def __init__( self, port, reactor ):
        self.port = port
        self.reactor = reactor

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
        print "Opening {} port for listening failed - bailign out".format( self.port )
        sys.exit( 0 )

    #############################
    def newConnection(self, conn):
        print "Gowno"
        pass
