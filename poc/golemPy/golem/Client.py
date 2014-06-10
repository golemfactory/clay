from twisted.internet import task

from golem.network.P2PService import P2PService
from golem.task.TaskServer import TaskServer
from golem.task.TaskManager import TaskManagerEventListener

from golem.core.hostaddress import getHostAddress

from golem.manager.NodeStateSnapshot import NodeStateSnapshot
from golem.manager.client.NodesManagerClient import NodesManagerClient

import time

from golem.AppConfig import AppConfig
from golem.Message import initMessages
from golem.ClientConfigDescriptor import ClientConfigDescriptor

def startClient( ):
    initMessages()

    cfg = AppConfig.loadConfig()

    optNumPeers     = cfg.getOptimalPeerNum()
    managerPort     = cfg.getManagerListenPort()
    startPort       = cfg.getStartPort()
    endPort         = cfg.getEndPort()
    seedHost        = cfg.getSeedHost()
    seedHostPort    = cfg.getSeedHostPort()
    sendPings       = cfg.getSendPings()
    pingsInterval   = cfg.getPingsInterval()
    clientUid       = cfg.getClientUid()
    addTasks        = cfg.getAddTasks()

    gettingPeersInterval    = cfg.getGettingPeersInterval()
    gettingTasksInterval    = cfg.getGettingTasksInterval()
    taskRequestInterval     = cfg.getTaskRequestInterval()
    estimatedPerformance    = cfg.getEstimatedPerformance()
    nodeSnapshotInterval    = cfg.getNodeSnapshotInterval()

    configDesc = ClientConfigDescriptor()

    configDesc.clientUid      = clientUid
    configDesc.startPort      = startPort
    configDesc.endPort        = endPort
    configDesc.managerPort    = managerPort
    configDesc.optNumPeers    = optNumPeers
    configDesc.sendPings      = sendPings
    configDesc.pingsInterval  = pingsInterval
    configDesc.addTasks       = addTasks
    configDesc.clientVersion  = 1

    configDesc.seedHost               = seedHost
    configDesc.seedHostPort           = seedHostPort

    configDesc.gettingPeersInterval   = gettingPeersInterval
    configDesc.gettingTasksInterval   = gettingTasksInterval
    configDesc.taskRequestInterval    = taskRequestInterval
    configDesc.estimatedPerformance   = estimatedPerformance
    configDesc.nodeSnapshotInterval   = nodeSnapshotInterval
    configDesc.maxResultsSendignDelay = cfg.getMaxResultsSendingDelay()

    print "Adding tasks {}".format( addTasks )
    print "Creating public client interface with uuid: {}".format( clientUid )
    c = Client( configDesc )

    print "Starting all asynchronous services"
    c.startNetwork( )

    return c

class GolemClientEventListener:
    ############################
    def __init__( self ):
        pass

    ############################
    def  taskUpdated( self, taskId ):
        pass


class ClientTaskManagerEventListener( TaskManagerEventListener ):
    #############################
    def __init__( self, client ):
        self.client = client

    #######################
    def taskStatusUpdated( self, taskId ):
        for l in self.client.listeners:
            l.taskUpdated( taskId )

class Client:

    ############################
    def __init__(self, configDesc ):

        self.configDesc     = configDesc

        self.lastPingTime   = 0.0
        self.p2service      = None
        self.taskServer     = None
        self.lastPingTime   = time.time()
        self.lastNSSTime    = time.time()

        self.lastNodeStateSnapshot = None

        self.hostAddress    = getHostAddress()

        self.nodesManagerClient = None

        self.doWorkTask     = task.LoopingCall(self.__doWork)
        self.doWorkTask.start(0.1, False)

        self.listeners      = []
       
    ############################
    def startNetwork( self ):
        print "Starting network ..."
        print "Starting p2p server ..."
        self.p2pservice = P2PService( self.hostAddress, self.configDesc )

        time.sleep( 1.0 )

        print "Starting task server ..."
        self.taskServer = TaskServer( self.hostAddress, self.configDesc )

        self.p2pservice.setTaskServer( self.taskServer )

        time.sleep( 0.5 )
        self.taskServer.taskManager.registerListener( ClientTaskManagerEventListener( self ) )
        print "Starting nodes manager client ..."
        self.nodesManagerClient = NodesManagerClient( self.configDesc.clientUid, "127.0.0.1", self.configDesc.managerPort, self.taskServer.taskManager )
        self.nodesManagerClient.start()

        #self.taskServer.taskManager.addNewTask( )

    ############################
    def stopNetwork(self):
        #FIXME: Pewnie cos tu trzeba jeszcze dodac. Zamykanie serwera i wysylanie DisconnectPackege
        self.p2pservice         = None
        self.taskServer         = None
        self.nodesManagerClient = None

    ############################
    def enqueueNewTask( self, task ):
        self.taskServer.taskManager.addNewTask( task )

    ############################
    def getId( self ):
        return self.configDesc.clientUid

    ############################
    def registerListener( self, listener ):
        assert isinstance( listener, GolemClientEventListener )
        self.listeners.append( listener )

    ############################
    def unregisterListener( self, listener ):
        assert isinstance( listener, GolemClientEventListener )
        for i in range( len( self.listeners ) ):
            if self.listeners[ i ] is listener:
                del self.listeners[ i ]
                return
        print "listener {} not registered".format( listener )

    def quarryTaskState( self, taskId ):
        return self.taskServer.taskManager.quarryTaskState( taskId )

    ############################
    def __doWork(self):
        if self.p2pservice:
            if self.configDesc.sendPings:
                self.p2pservice.pingPeers( self.pingsInterval )

            self.p2pservice.syncNetwork()
            self.taskServer.syncNetwork()

            if time.time() - self.lastNSSTime > self.configDesc.nodeSnapshotInterval:
                self.__makeNodeStateSnapshot()
                self.lastNSSTime = time.time()

                #self.managerServer.sendStateMessage( self.lastNodeStateSnapshot )

    ############################
    def __makeNodeStateSnapshot( self, isRunning = True ):

        peersNum            = len( self.p2pservice.peers )
        lastNetworkMessages = self.p2pservice.getLastMessages()

        if self.taskServer:
            tasksNum                = len( self.taskServer.taskHeaders )
            remoteTasksProgresses   = self.taskServer.taskComputer.getProgresses()
            localTasksProgresses    = self.taskServer.taskManager.getProgresses()
            lastTaskMessages        = self.taskServer.getLastMessages()
            self.lastNodeStateSnapshot = NodeStateSnapshot(     isRunning
                                                           ,    self.configDesc.clientUid
                                                           ,    peersNum
                                                           ,    tasksNum
                                                           ,    self.p2pservice.hostAddress
                                                           ,    self.p2pservice.p2pServer.curPort
                                                           ,    lastNetworkMessages
                                                           ,    lastTaskMessages
                                                           ,    remoteTasksProgresses  
                                                           ,    localTasksProgresses )
        else:
            self.lastNodeStateSnapshot = NodeStateSnapshot( self.configDesc.clientUid, peersNum )

        if self.nodesManagerClient:
            self.nodesManagerClient.sendClientStateSnapshot( self.lastNodeStateSnapshot )