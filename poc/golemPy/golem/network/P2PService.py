
from P2PServer import P2PServer
from golem.core.network import Network
from PeerSession import PeerSession
import time
import logging

logger = logging.getLogger(__name__)

class P2PService:
    ########################
    def __init__( self, hostAddress, configDesc ):

        self.p2pServer              = P2PServer( configDesc, self )

        self.configDesc             = configDesc

        self.peers                  = {}
        self.allPeers               = []
        self.clientUid              = self.configDesc.clientUid
        self.lastPeersRequest       = time.time()
        self.lastGetTasksRequest    = time.time()
        self.incommingPeers         = {}
        self.freePeers              = []
        self.taskServer             = None
        self.hostAddress            = hostAddress

        self.lastMessages           = []

        if len( self.configDesc.seedHost ) > 0:
            self.__connect( self.configDesc.seedHost, self.configDesc.seedHostPort )

    #############################
    def setTaskServer( self, taskServer ):
        self.taskServer = taskServer

    #############################
    def syncNetwork( self ):

        self.__sendMessageGetPeers()

        if self.taskServer:
            self.__sendMessageGetTasks()

    #############################
    def newSession( self, session ):
        session.p2pService = self
        self.allPeers.append( session )
        session.start()
 
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

        if peerSession in self.allPeers:
            self.allPeers.remove( peerSession )

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
    def __connect( self, address, port ):

        Network.connect( address, port, PeerSession, self.__connectionEstablished, self.__connectionFailure )

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
            logger.info( "Connecting to peer {}".format( self.freePeers[ x ] ) )
            self.__connect( self.incommingPeers[ self.freePeers[ x ] ][ "address" ], self.incommingPeers[ self.freePeers[ x ] ][ "port" ] )
            self.freePeers.remove( self.freePeers[ x ] )

    #############################
    def __sendMessageGetTasks( self ):
        if time.time() - self.lastGetTasksRequest > 2:
            self.lastGetTasksRequest = time.time()
            for p in self.peers.values():
                p.sendGetTasks()

    #############################
    def __connectionEstablished( self, session ):
        session.p2pService = self
        self.allPeers.append( session )
        logger.info( "Connection to peer established. {}: {}".format( session.conn.transport.getPeer().host, session.conn.transport.getPeer().port ) )

    #############################
    def __connectionFailure( self ):
        logger.error( "Connection to peer failure." )
