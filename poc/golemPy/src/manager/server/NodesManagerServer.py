from twisted.internet.protocol import Factory
from twisted.internet.endpoints import TCP4ServerEndpoint, connectProtocol

from ServerManagerSession import ServerManagerSession
from ServerManagerConnState import ServerManagerConnState
from nodestatesnapshot import NodeStateSnapshot

class NodesManagerServer:

    #############################
    def __init__( self, nodesManager, port, reactor = None ):
        self.port               = port
        self.managerSessions    = []
        self.reactor            = reactor
        self.nodesManager       = nodesManager

    #############################
    def setReactor( self, reactor ):
        self.reactor = reactor
        self.__startAccepting()

    #############################
    def __startAccepting( self ):
        self.__runListenOnce()

    #############################
    def __runListenOnce( self ):
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

    #############################
    def newNMConnection(self, conn):
        pp = conn.transport.getPeer()
        ms = ServerManagerSession( conn, self,  pp.host, pp.port )
        conn.setSession( ms )
        self.managerSessions.append( ms )

    #############################
    def nodeStateSnapshotReceived( self, nss ):
        self.nodesManager.appendStateUpdate( nss )
        
    #############################
    def managerSessionDisconnected( self, uid ):
        self.nodesManager.appendStateUpdate( NodeStateSnapshot( False, uid ) )

    #############################
    def sendTerminate( self, uid ):
        for ms in self.managerSessions:
            if ms.uid == uid:
                ms.sendKillNode()

    #############################
    def sendNewTask( self, uid, task ):
        for ms in self.managerSessions:
            if ms.uid == uid:
                ms.sendNewTask( task )


class ManagerServerFactory(Factory):
    #############################
    def __init__( self, server ):
        self.server = server

    #############################
    def buildProtocol( self, addr ):
        print "Protocol build for {} : {}".format( addr.host, addr.port )
        cs = ServerManagerConnState( self.server )
        return cs