
from ClientManagerSession import ClientManagerSession
from ClientManagerConnState import ClientManagerConnState
from network import Network

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

    ######################
    def addNewTask( self, task ):
        task.returnAddress  = self.taskManager.listenAddress
        task.returnPort     = self.taskManager.listenPort

        self.taskManager.addNewTask( task )

    ######################
    def __connectNodesManager( self ):

        assert not self.clientManagerSession # connection already established

        Network.connect( self.mangerServerAddress, self.mangerServerPort, ClientManagerSession, self.__connectionEstablished, self.__connectionFailure )


    #############################
    def __connectionEstablished( self, session ):
        session.client = self
        self.clientManagerSession = session

    def __connectionFailure( self ):
        print "Connection to nodes manager failure."