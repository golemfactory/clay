from twisted.internet.endpoints import TCP4ServerEndpoint, TCP4ClientEndpoint, connectProtocol
import logging

logger = logging.getLogger(__name__)

class Network:

    ######################
    @classmethod
    def connect( cls, address, port, SessionType, establishedCallback = None, failureCallback = None, *args ):
        logger.debug( "Connecting to host {} : {}".format( address, port ) )
        from twisted.internet import reactor
        endpoint    = TCP4ClientEndpoint( reactor, address, port )
        connection  = SessionType.ConnectionStateType()

        d = connectProtocol( endpoint, connection )

        d.addCallback( Network.__connectionEstablished, SessionType, establishedCallback, *args )
        d.addErrback( Network.__connectionFailure, failureCallback, *args )

    ######################
    @classmethod
    def listen( cls, portStart, portEnd, factory, ownReactor = None, establishedCallback = None, failureCallback = None  ):

        Network.__listenOnce( portStart, portEnd, factory, ownReactor, establishedCallback, failureCallback )

    ######################
    @classmethod
    def __listenOnce( cls, port, portEnd, factory, ownReactor = None, establishedCallback = None, failureCallback = None ):
        if ownReactor:
            ep = TCP4ServerEndpoint( ownReactor, port )
        else:
            from twisted.internet import reactor
            ep = TCP4ServerEndpoint( reactor, port )


        d = ep.listen( factory )

        d.addCallback( cls.__listeningEstablished, establishedCallback )
        d.addErrback( cls.__listeningFailure, port, portEnd, factory, ownReactor, establishedCallback, failureCallback )
        pass

    ######################
    @classmethod
    def __connectionEstablished( cls, conn, SessionType, establishedCallback, *args ):
        if conn:
            session = SessionType( conn )
            conn.setSession( session )

            pp = conn.transport.getPeer()
            logger.debug( "ConnectionEstablished {} {}".format( pp.host, pp.port ) )

            if establishedCallback:
                if len( args ) == 0:
                    establishedCallback( session )
                else:
                    establishedCallback( session, *args )

    ######################
    @classmethod
    def __connectionFailure( cls, conn, failureCallback, *args ):
        logger.info( "Connection failure. {}".format( conn ) )
        if failureCallback:
            if len( args ) == 0:
                failureCallback()
            else:
                failureCallback( *args )


    ######################
    @classmethod
    def __listeningEstablished( cls, iListeningPort, establishedCallback ):
        if establishedCallback:
            establishedCallback( iListeningPort )


    @classmethod
    ######################
    def __listeningFailure( cls, p, curPort, endPort, factory, ownReactor, establishedCallback, failureCallback ):
        if curPort < endPort:
            curPort += 1
            Network.__listenOnce( curPort, endPort, factory, ownReactor, establishedCallback, failureCallback  )
        else:
            if failureCallback:
                failureCallback( p )