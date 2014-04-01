from managersession import ClientManagerSession

class NodesManagerClient:

    ######################
    def __init__( self, clientUid, mangerServerAddress, mangerServerPort ):
        self.clientUid              = clientUid
        self.mangerServerAddress    = mangerServerAddress
        self.mangerServerPort       = mangerServerPort
        self.clientManagerSession   = None
    
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
    def __connectNodesManager( self ):

        assert not self.clientManagerSession # connection already established

        print "Connecting to nodes manager host {} : {}".format( address ,port )
        endpoint    = TCP4ClientEndpoint( reactor, self.mangerServerAddress, self.configDesc.managerPort )
        connection  = ManagerConnectionState( self );

        d = connectProtocol( endpoint, connection )

        d.addCallback( self.__connectionEstablished )
        d.addErrback( self.__connectionFailure )

    #############################
    def __connectionEstablished( self, conn ):
        if conn:
            self.clientManagerSession = ClientManagerSession( conn, self )
            pp = conn.transport.getPeer()
            print "__connectionNMEstablished {} {}".format( pp.host, pp.port )

    def __connectionFailure( self, conn ):
        print "Connection to nodes manager failure."