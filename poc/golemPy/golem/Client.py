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

import logging

logger = logging.getLogger(__name__)

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
    rootPath        = cfg.getRootPath()
    numCores        = cfg.getNumCores()
    maxResourceSize = cfg.getMaxResourceSize()
    maxMemorySize   = cfg.getMaxMemorySize()

    gettingPeersInterval    = cfg.getGettingPeersInterval()
    gettingTasksInterval    = cfg.getGettingTasksInterval()
    taskRequestInterval     = cfg.getTaskRequestInterval()
    estimatedPerformance    = cfg.getEstimatedPerformance()
    nodeSnapshotInterval    = cfg.getNodeSnapshotInterval()

    configDesc = ClientConfigDescriptor()

    configDesc.clientUid        = clientUid
    configDesc.startPort        = startPort
    configDesc.endPort          = endPort
    configDesc.managerPort      = managerPort
    configDesc.optNumPeers      = optNumPeers
    configDesc.sendPings        = sendPings
    configDesc.pingsInterval    = pingsInterval
    configDesc.addTasks         = addTasks
    configDesc.clientVersion    = 1
    configDesc.rootPath         = rootPath
    configDesc.numCores         = numCores
    configDesc.maxResourceSize  = maxResourceSize
    configDesc.maxMemorySize    = maxMemorySize

    configDesc.seedHost               = seedHost
    configDesc.seedHostPort           = seedHostPort

    configDesc.gettingPeersInterval   = gettingPeersInterval
    configDesc.gettingTasksInterval   = gettingTasksInterval
    configDesc.taskRequestInterval    = taskRequestInterval
    configDesc.estimatedPerformance   = estimatedPerformance
    configDesc.nodeSnapshotInterval   = nodeSnapshotInterval
    configDesc.maxResultsSendingDelay = cfg.getMaxResultsSendingDelay()

    logger.info( "Adding tasks {}".format( addTasks ) )
    logger.info( "Creating public client interface with uuid: {}".format( clientUid ) )
    c = Client( configDesc, config = cfg )

    logger.info( "Starting all asynchronous services" )
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
    def __init__(self, configDesc, rootPath = "", config = "" ):

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

        self.rootPath = rootPath
        self.cfg = config
       
    ############################
    def startNetwork( self ):
        logger.info( "Starting network ..." )
        logger.info( "Starting p2p server ..." )
        self.p2pservice = P2PService( self.hostAddress, self.configDesc )

        time.sleep( 1.0 )

        logger.info( "Starting task server ..." )
        self.taskServer = TaskServer( self.hostAddress, self.configDesc )

        self.p2pservice.setTaskServer( self.taskServer )

        time.sleep( 0.5 )
        self.taskServer.taskManager.registerListener( ClientTaskManagerEventListener( self ) )
        logger.info( "Starting nodes manager client ..." )
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
    def abortTask( self, taskId ):
        self.taskServer.taskManager.abortTask( taskId )

    ############################
    def restartTask( self, taskId ):
        self.taskServer.taskManager.restartTask( taskId )

    ############################
    def pauseTask( self, taskId ):
        self.taskServer.taskManager.pauseTask( taskId )

    ############################
    def resumeTask( self, taskId ):
        self.taskServer.taskManager.resumeTask( taskId )

    ############################
    def deleteTask( self, taskId ):
        self.taskServer.removeTaskHeader( taskId )
        self.taskServer.taskManager.deleteTask( taskId )

    ############################
    def getId( self ):
        return self.configDesc.clientUid

    ############################
    def getRootPath( self ):
        return self.configDesc.rootPath

    ############################
    def registerListener( self, listener ):
        assert isinstance( listener, GolemClientEventListener )
        self.listeners.append( listener )

    ############################
    def changeConfig( self, hostAddress, hostPort, workingDirectory, managerPort, numCores, estimatedPerformance, maxResourceSize, maxMemorySize ):
        self.cfg.changeConfig( hostAddress, hostPort, workingDirectory, managerPort, numCores, estimatedPerformance, maxResourceSize, maxMemorySize  )
        self.configDesc.seedHost = hostAddress
        try:
            self.configDesc.seedHostPort = int( hostPort )
        except:
            logger.warning( "{} is not a proper port number".format( hostPort ) )
            self.configDesc.seedHostPort = ""
        self.configDesc.rootPath = workingDirectory
        try:
            self.configDesc.managerPort = int( managerPort )
        except:
            logger.warning( "{} is not a proper port number".format( hostPort ) )
            self.configDesc.managerPort = ""
        self.configDesc.numCores = numCores
        self.configDesc.estimatedPerformance = estimatedPerformance
        self.configDesc.maxResourceSize = maxResourceSize
        self.configDesc.maxMemorySize   = maxMemorySize

        self.p2pservice.changeConfig( self.configDesc )
        self.taskServer.changeConfig( self.configDesc )

        del self.nodesManagerClient
        self.nodesManagerClient = NodesManagerClient( self.configDesc.clientUid, "127.0.0.1", self.configDesc.managerPort, self.taskServer.taskManager )
        self.nodesManagerClient.start()

    ############################
    def unregisterListener( self, listener ):
        assert isinstance( listener, GolemClientEventListener )
        for i in range( len( self.listeners ) ):
            if self.listeners[ i ] is listener:
                del self.listeners[ i ]
                return
        logger.info( "listener {} not registered".format( listener ) )

    def querryTaskState( self, taskId ):
        return self.taskServer.taskManager.querryTaskState( taskId )

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

    def getStatus(self):
        progress = self.taskServer.taskComputer.getProgresses()
        if len( progress ) > 0:
            msg =  "Counting {} subtask(s):".format(len(progress))
            for k, v in progress.iteritems():
                msg = "{} \n {} ({}%) ".format( msg, k, v.getProgress() * 100 )
            return msg
        return "Waiting for tasks..."