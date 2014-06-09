
from golem.core.network import Network
from golem.manager.NodeStateSnapshot import NodeStateSnapshot

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
        Network.listen( self.port, self.port, ManagerServerFactory( self ), self.reactor, self.__listeningEstablished, self.__listeningFailure )

    #############################
    def __listeningEstablished( self, port ):
        assert port == self.port
        print "Manager server - port {} opened, listening".format( port )

    #############################
    def __listeningFailure( self ):
        print "Opening {} port for listening failed - bailign out".format( self.port )

    #############################
    def newConnection( self, session ):
        self.managerSessions.append( session )

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


from twisted.internet.protocol import Factory
from ServerManagerConnState import ServerManagerConnState

class ManagerServerFactory(Factory):
    #############################
    def __init__( self, server ):
        self.server = server

    #############################
    def buildProtocol( self, addr ):
        print "Protocol build for {} : {}".format( addr.host, addr.port )
        cs = ServerManagerConnState( self.server )
        return cs