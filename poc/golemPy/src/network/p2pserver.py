from network import Network
import time

class P2PServer:
    #############################
    def __init__( self, hostAddress, configDesc, p2pService ):

        self.configDesc             = configDesc
        self.p2pService             = p2pService
        self.curPort                = 0

        self.__startAccepting()

    #############################
    def newConnection( self, session ):
        self.p2pService.newSession( session )
                                   
    #############################
    def __startAccepting( self ):
        print "Enabling network accepting state"

        Network.listen( self.configDesc.startPort, self.configDesc.endPort, NetServerFactory( self ), None, self.__listeningEstablished, self.__listeningFailure )

    #############################
    def __listeningEstablished( self, port ):
        self.curPort = port
        print "Port {} opened - listening".format( port )

    #############################
    def __listeningFailure( self ):
        print "Listening on ports {} to {} failure".format( self.configDesc.startPort, self.configDesc.endPort )



from twisted.internet.protocol import Factory
from netconnstate import NetConnState

class NetServerFactory( Factory ):
    #############################
    def __init__( self, p2pserver ):
        self.p2pserver = p2pserver

    #############################
    def buildProtocol( self, addr ):
        print "Protocol build for {}".format( addr )
        return NetConnState( self.p2pserver )

