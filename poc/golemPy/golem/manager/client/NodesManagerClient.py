
from ClientManagerSession import ClientManagerSession
from golem.core.network import Network

import logging

logger = logging.getLogger(__name__)

class NodesManagerClient:

    ######################
    def __init__( self, clientUid, managerServerAddress, managerServerPort, taskManager, logic = None ):
        self.clientUid              = clientUid
        self.managerServerAddress    = managerServerAddress
        self.managerServerPort       = managerServerPort
        self.clientManagerSession   = None
        self.logic                  = logic
        self.taskManager            = taskManager

    ######################
    def start( self ):
        try:
            if (int( self.managerServerPort ) < 1) or ( int( self.managerServerPort ) > 65535 ):
                logger.warning( u"Manager Server port number out of range [1, 65535]: {}".format( self.managerServerPort ) )
                return True
        except Exception, e:
            logger.error( u"Wrong seed port number {}: {}".format( self.managerServerPort, str( e ) ) )
            return True

        self.__connectNodesManager()

    #############################
    def sendClientStateSnapshot( self, snapshot ):
        if self.clientManagerSession:
            self.clientManagerSession.sendClientStateSnapshot( snapshot )

    ######################
    def addNewTask( self, task ):
        if self.logic:
            self.logic.addTaskFromDefinition( task )
        elif self.taskManager:
            task.returnAddress  = self.taskManager.listenAddress
            task.returnPort     = self.taskManager.listenPort
            self.taskManager.addNewTask( task )
        else:
            logger.error("No logic and no taskManager defined.")

    ######################
    def runNewNodes( self, num ):
        self.logic.addNewNodesFunction( num )

    def dropConnection( self ):
        if  self.clientManagerSession:
            self.clientManagerSession.dropped()


    ######################
    def __connectNodesManager( self ):

        assert not self.clientManagerSession # connection already established

        Network.connect( self.managerServerAddress, self.managerServerPort, ClientManagerSession, self.__connectionEstablished, self.__connectionFailure )


    #############################
    def __connectionEstablished( self, session ):
        session.client = self
        self.clientManagerSession = session

    def __connectionFailure( self ):
        logger.error( "Connection to nodes manager failure." )