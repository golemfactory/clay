from twisted.internet.endpoints import TCP4ServerEndpoint, TCP4ClientEndpoint, connectProtocol
import logging

logger = logging.getLogger(__name__)

class Network:

    ######################
    @classmethod
    def connect( self, address, port, SessionType, establishedCallback = None, failureCallback = None, *args ):
        logger.info( "Connecting to host {} : {}".format( address, port ) )
        from twisted.internet import reactor
        endpoint    = TCP4ClientEndpoint( reactor, address, port )
        connection  = SessionType.ConnectionStateType();

        d = connectProtocol( endpoint, connection )

        d.addCallback( Network.__connectionEstablished, SessionType, establishedCallback, *args )
        d.addErrback( Network.__connectionFailure, failureCallback, *args )

    ######################
    @classmethod
    def listen( self, portStart, portEnd, factory, ownReactor = None, establishedCallback = None, failureCallback = None  ):

        Network.__listenOnce( portStart, portEnd, factory, ownReactor, establishedCallback, failureCallback )

    ######################
    @classmethod
    def __listenOnce( self, port, portEnd, factory, ownReactor = None, establishedCallback = None, failureCallback = None ):
        if ownReactor:
            ep = TCP4ServerEndpoint( ownReactor, port )
        else:
            from twisted.internet import reactor
            ep = TCP4ServerEndpoint( reactor, port )


        d = ep.listen( factory )
        
        d.addCallback( self.__listeningEstablished, establishedCallback )
        d.addErrback( self.__listeningFailure, port, portEnd, factory, ownReactor, establishedCallback, failureCallback )
        pass

    ######################
    @classmethod
    def __connectionEstablished( self, conn, SessionType, establishedCallback, *args ):
        if conn:
            session = SessionType( conn )
            conn.setSession( session )

            pp = conn.transport.getPeer()
            logger.info( "__connectionEstablished {} {}".format( pp.host, pp.port ) )

            if establishedCallback:
                if len( args ) == 0:
                    establishedCallback( session )
                else:
                    establishedCallback( session, *args )

    ######################
    @classmethod
    def __connectionFailure( self, conn, failureCallback, *args ):
        logger.info( "Connection failure. {}".format( conn ) )
        if failureCallback:
            if len( args ) == 0:
                failureCallback()
            else:
                failureCallback( *args )
        

    ######################
    @classmethod
    def __listeningEstablished( self, p, establishedCallback ):
        if establishedCallback:
            establishedCallback( p.getHost().port )
        

    @classmethod
    ######################
    def __listeningFailure( self, p, curPort, endPort, factory, ownReactor, establishedCallback, failureCallback ):
        if curPort < endPort:
            curPort += 1
            Network.__listenOnce( curPort, endPort, factory, ownReactor, establishedCallback, failureCallback  )
        else:
            if failureCallback:
                failureCallback()
