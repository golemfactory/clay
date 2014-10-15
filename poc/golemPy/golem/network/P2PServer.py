import logging

from golem.network.transport.Tcp import Network
from poc.golemPy.golem.network.p2p.NetConnState import NetConnState


logger = logging.getLogger(__name__)

class P2PServer:
    #############################
    def __init__( self, configDesc, p2pService ):

        self.configDesc             = configDesc
        self.p2pService             = p2pService
        self.curPort                = 0

        self.__startAccepting()

    #############################
    def newConnection( self, session ):
        self.p2pService.newSession( session )

    #############################
    def changeConfig( self, configDesc ):
        self.configDesc = configDesc

    #############################
    def __startAccepting( self ):
        logger.info( "Enabling network accepting state" )

        Network.listen( self.configDesc.startPort, self.configDesc.endPort, NetServerFactory( self ), None, self.__listeningEstablished, self.__listeningFailure )

    #############################
    def __listeningEstablished( self, port ):
        self.curPort = port
        logger.info( "Port {} opened - listening".format( port ) )

    #############################
    def __listeningFailure( self ):
        logger.error( "Listening on ports {} to {} failure".format( self.configDesc.startPort, self.configDesc.endPort ) )



from twisted.internet.protocol import Factory


class NetServerFactory( Factory ):
    #############################
    def __init__( self, p2pserver ):
        self.p2pserver = p2pserver

    #############################
    def buildProtocol( self, addr ):
        logger.info( "Protocol build for {}".format( addr ) )
        return NetConnState( self.p2pserver )

