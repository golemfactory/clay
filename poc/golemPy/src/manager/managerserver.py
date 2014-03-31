from twisted.internet import reactor
from twisted.internet.protocol import Factory
from twisted.internet.endpoints import TCP4ServerEndpoint, TCP4ClientEndpoint, connectProtocol

class ManagerServerFactory(Factory):
    #############################
    def __init__(self, server):
        self.server = server

    #############################
    def buildProtocol(self, addr):
        print "Protocol build for {}".format(addr)
        return ManagerConnectopmState(self.server)

class ManagerServer:
    
    #############################
    def __init__( self, port ):
        self.port = port
        self.__startAccepting()

    #############################
    def __startAccepting(self):
        print "Enabling tasks accepting state"
        self.__runListenOnce()

    #############################
    def __runListenOnce( self ):
        ep = TCP4ServerEndpoint( reactor, self.port )
        
        d = ep.listen( ManagerServerFactory( self ) )
        
        d.addCallback( self.__listeningEstablished )
        d.addErrback( self.__listeningFailure )

    #############################
    def __listeningEstablished(self, p):
        assert p.getHost().port == self.port
        print "Manager server - port {} opened, listening".format(p.getHost().port)

    #############################
    def __listeningFailure(self, p):
        print "Opening {} port for listening failed, trying the next one".format( self.curPort )

        self.curPort = self.curPort + 1

        if self.curPort <= self.configDesc.endPort:
            self.__runListenOnce()
        else:
            #FIXME: some graceful terminations should take place here
            sys.exit(0)
