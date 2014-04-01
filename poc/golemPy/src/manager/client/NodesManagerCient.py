from ClientManagerSession import ClientManagerSession
from ClientManagerConnState import ClientManagerConnState

from twisted.internet.endpoints import TCP4ClientEndpoint, connectProtocol
from twisted.internet import reactor

class NodesManagerClient:

    ######################
    def __init__( self, clientUid, mangerServerAddress, mangerServerPort, taskManager ):
        self.clientUid              = clientUid
        self.mangerServerAddress    = mangerServerAddress
        self.mangerServerPort       = mangerServerPort
        self.clientManagerSession   = None
        self.taskManager            = taskManager
    
    ######################
    def start( self ):
        self.__connectNodesManager()

    #############################
    def sendClientStateSnapshot( self, snapshot ):
        if self.clientManagerSession:
            self.clientManagerSession.sendClientStateSnapshot( snapshot )
        else:
            print "Cannot send snapshot !!! No connection with manager"

    ######################
    def addNewTask( self, task ):
        self.taskManager.addNewTask( task )

    ######################
    def __connectNodesManager( self ):

        assert not self.clientManagerSession # connection already established

        print "Connecting to nodes manager host {} : {}".format( self.mangerServerAddress, self.mangerServerPort )
        endpoint    = TCP4ClientEndpoint( reactor, self.mangerServerAddress, self.mangerServerPort )
        connection  = ClientManagerConnState();

        d = connectProtocol( endpoint, connection )

        d.addCallback( self.__connectionEstablished )
        d.addErrback( self.__connectionFailure )

    #############################
    def __connectionEstablished( self, conn ):
        if conn:
            self.clientManagerSession = ClientManagerSession( conn, self )
            conn.setSession( self.clientManagerSession )
            pp = conn.transport.getPeer()
            print "__connectionNMEstablished {} {}".format( pp.host, pp.port )

    def __connectionFailure( self, conn ):
        print "Connection to nodes manager failure."