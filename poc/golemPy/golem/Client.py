from twisted.internet import task
from threading import Lock

from golem.network.p2p.P2PService import P2PService
from golem.task.TaskServer import TaskServer
from golem.task.TaskManager import TaskManagerEventListener

from golem.core.hostaddress import getHostAddress

from golem.manager.NodeStateSnapshot import NodeStateSnapshot

import time

from golem.AppConfig import AppConfig
from golem.BankConfig import BankConfig
from golem.Model import Database, Node, Bank
from golem.Message import initMessages
from golem.ClientConfigDescriptor import ClientConfigDescriptor
from golem.environments.EnvironmentsManager import EnvironmentsManager
from golem.resource.ResourceServer import ResourceServer
from golem.resource.DirManager import DirManager

import logging

logger = logging.getLogger(__name__)

def emptyAddNodes( *args ):
    pass

def startClient():
    initMessages()

    cfg = AppConfig.loadConfig()

    optNumPeers     = cfg.getOptimalPeerNum()
    managerAddress  = cfg.getManagerAddress()
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
    distResNum      = cfg.getDistributedResNum()
    appName         = cfg.getAppName()
    appVersion      = cfg.getAppVersion()

    gettingPeersInterval        = cfg.getGettingPeersInterval()
    gettingTasksInterval        = cfg.getGettingTasksInterval()
    taskRequestInterval         = cfg.getTaskRequestInterval()
    useWaitingForTaskTimeout    = cfg.getUseWaitingForTaskTimeout()
    waitingForTaskTimeout       = cfg.getWaitingForTaskTimeout()
    estimatedPerformance        = cfg.getEstimatedPerformance()
    nodeSnapshotInterval        = cfg.getNodeSnapshotInterval()
    useDistributedResourceManagement = cfg.getUseDistributedResourceManagement()

    configDesc = ClientConfigDescriptor()

    configDesc.clientUid        = clientUid
    configDesc.startPort        = startPort
    configDesc.endPort          = endPort
    configDesc.managerAddress   = managerAddress
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
    configDesc.distResNum       = distResNum

    configDesc.seedHost               = seedHost
    configDesc.seedHostPort           = seedHostPort

    configDesc.appVersion             = appVersion
    configDesc.appName                = appName

    configDesc.gettingPeersInterval     = gettingPeersInterval
    configDesc.gettingTasksInterval     = gettingTasksInterval
    configDesc.taskRequestInterval      = taskRequestInterval
    configDesc.useWaitingForTaskTimeout = useWaitingForTaskTimeout
    configDesc.waitingForTaskTimeout    = waitingForTaskTimeout
    configDesc.estimatedPerformance     = estimatedPerformance
    configDesc.nodeSnapshotInterval     = nodeSnapshotInterval
    configDesc.maxResultsSendingDelay   = cfg.getMaxResultsSendingDelay()
    configDesc.useDistributedResourceManagement = useDistributedResourceManagement

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
    def taskUpdated( self, taskId ):
        pass

    ############################
    def networkConnected( self ):
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

        self.hostAddress    = getHostAddress( self.configDesc.seedHost )

        self.nodesManagerClient = None

        self.doWorkTask     = task.LoopingCall(self.__doWork)
        self.doWorkTask.start(0.1, False)

        self.listeners      = []

        self.rootPath = rootPath
        self.cfg = config
        self.sendSnapshot = False
        self.snapshotLock = Lock()

        self.db = Database()
        self.db.checkNode( self.configDesc.clientUid )


        #self.bankConfig = BankConfig.loadConfig( self.configDesc.clientUid )
        #self.budget = self.bankConfig.getBudget()
        #self.priceBase = self.bankConfig.getPriceBase()
        self.budget = Bank.get(Bank.nodeId == self.configDesc.clientUid ).val
        self.priceBase = 10.0

        self.environmentsManager = EnvironmentsManager()

        self.resourceServer = None
        self.resourcePort   = 0
        self.lastGetResourcePeersTime  = time.time()
        self.getResourcePeersInterval = 5.0
       
    ############################
    def startNetwork( self ):
        logger.info( "Starting network ..." )

        logger.info( "Starting p2p server ..." )
        self.p2pservice = P2PService( self.hostAddress, self.configDesc )
        time.sleep( 1.0 )

        logger.info( "Starting resource server..." )
        self.resourceServer = ResourceServer( self.configDesc, self )
        time.sleep( 1.0 )
        self.p2pservice.setResourceServer( self.resourceServer )

        logger.info( "Starting task server ..." )
        self.taskServer = TaskServer( self.hostAddress, self.configDesc, self )

        self.p2pservice.setTaskServer( self.taskServer )

        time.sleep( 0.5 )
        self.taskServer.taskManager.registerListener( ClientTaskManagerEventListener( self ) )
        #logger.info( "Starting nodes manager client ..." )

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
        if self.configDesc.useDistributedResourceManagement:
            self.getResourcePeers()
            resFiles = self.resourceServer.addFilesToSend( task.taskResources, task.header.taskId, self.configDesc.distResNum )
            task.setResFiles( resFiles )

    ############################
    def getResourcePeers( self ):
        self.p2pservice.sendGetResourcePeers()

    ############################
    def taskResourcesSend( self, taskId ):
        self.taskServer.taskManager.resourcesSend( taskId )

    ############################
    def taskResourcesCollected( self, taskId ):
        self.taskServer.taskComputer.taskResourceCollected( taskId )

    ############################
    def setResourcePort ( self, resourcePort ):
        self.resourcePort = resourcePort
        self.p2pservice.setResourcePeer( self.hostAddress, self.resourcePort )

    ############################
    def abortTask( self, taskId ):
        self.taskServer.taskManager.abortTask( taskId )

    ############################
    def restartTask( self, taskId ):
        self.taskServer.taskManager.restartTask( taskId )

    ############################
    def restartSubtask( self, subtaskId ):
        self.taskServer.taskManager.restartSubtask( subtaskId )

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
    def payForTask( self, priceMod ):
        price = int( round( priceMod * self.priceBase ) )
        if self.budget >= price:
#            self.bankConfig.addToBudget( -price )
            self.budget -= price
            Bank.update(val = self.budget ).where( Bank.nodeId == self.configDesc.clientUid ).execute()
            return price
        else:
            logger.warning( "Not enough money to pay for task. ")
            return 0

    ############################
    def getReward( self, reward ):
#        self.bankConfig.addToBudget( reward )
        self.budget += reward
        Bank.update(val = self.budget ).where( Bank.nodeId == self.configDesc.clientUid ).execute()

    ############################
    def registerListener( self, listener ):
        assert isinstance( listener, GolemClientEventListener )
        self.listeners.append( listener )

    ############################
    def changeConfig( self, newConfigDesc ):
        self.cfg.changeConfig( newConfigDesc )
        self.configDesc.seedHost = newConfigDesc.seedHost
        try:
            self.configDesc.seedHostPort = int( newConfigDesc.seedHostPort )
        except:
            logger.warning( "{} is not a proper port number".format( newConfigDesc.seedHostPort ) )
            self.configDesc.seedHostPort = ""
        if self.configDesc.rootPath != newConfigDesc.rootPath:
            self.resourceServer.changeResourceDir( newConfigDesc )
        self.configDesc.rootPath = newConfigDesc.rootPath
        try:
            self.configDesc.managerPort = int( newConfigDesc.managerPort )
        except:
            logger.warning( "{} is not a proper port number".format( newConfigDesc.managerPort ) )
            self.configDesc.managerPort = ""
        self.configDesc.numCores = newConfigDesc.numCores
        self.configDesc.estimatedPerformance = newConfigDesc.estimatedPerformance
        self.configDesc.maxResourceSize = newConfigDesc.maxResourceSize
        self.configDesc.maxMemorySize   = newConfigDesc.maxMemorySize

        try:
            self.configDesc.optNumPeers = int( newConfigDesc.optNumPeers )
        except ValueError:
            logger.warning( "Opt peer number '{}' is not a number".format( newConfigDesc.optNumPeers ) )

        self.configDesc.useDistributedResourceManagement = newConfigDesc.useDistributedResourceManagement

        try:
            self.configDesc.distResNum = int( newConfigDesc.distResNum )
        except ValueError:
            logger.warning( "Distributed resource number '{}' is not a number".format( newConfigDesc.optNumPeers ) )

        self.configDesc.useWaitingForTaskTimeout = newConfigDesc.useWaitingForTaskTimeout
        try:
            self.configDesc.waitingForTaskTimeout = float( newConfigDesc.waitingForTaskTimeout )
        except ValueError:
            logger.warning( "Waiting for task timeout '{}' is not a number".format( newConfigDesc.waitingForTaskTimeout ) )

        self.configDesc.sendPings = newConfigDesc.sendPings
        try:
            self.configDesc.pingsInterval = float( newConfigDesc.pingsInterval )
        except ValueError:
            logger.warning( "Pings interval '{}' is not a number".format( newConfigDesc.pingsInterval ) )

        try:
            self.configDesc.gettingPeersInterval = float( newConfigDesc.gettingPeersInterval )
        except ValueError:
            logger.warning( "Getting peers interval '{}' is not a number".format( newConfigDesc.gettingPeersInterval ) )

        try:
            self.configDesc.gettingTasksInterval = float( newConfigDesc.gettingTasksInterval )
        except ValueError:
            logger.warning( "Getting tasks interval '{}' is not a number".format( newConfigDesc.gettingTasksInterval ) )

        try:
            self.configDesc.nodeSnapshotInterval = float( newConfigDesc.nodeSnapshotInterval )
        except ValueError:
            logger.warning( "Node snapshot interval '{}' is not a number".format( newConfigDesc.nodeSnapshotInterval ) )

        try:
            self.configDesc.maxResultsSendingDelay = float( newConfigDesc.maxResultsSendingDelay )
        except ValueError:
            logger.warning( "Max result sending delay '{}' is not a number".format( newConfigDesc.maxResultsSendingDelay ) )


        self.p2pservice.changeConfig( self.configDesc )
        self.taskServer.changeConfig( self.configDesc )

    ############################
    def registerNodesManagerClient( self, nodesManagerClient ):
        self.nodesManagerClient = nodesManagerClient

    ############################
    def changeTimeouts(self, taskId, fullTaskTimeout, subtaskTimeout, minSubtaskTime ):
        self.taskServer.changeTimeouts( taskId, fullTaskTimeout, subtaskTimeout, minSubtaskTime )

    ############################
    def unregisterListener( self, listener ):
        assert isinstance( listener, GolemClientEventListener )
        for i in range( len( self.listeners ) ):
            if self.listeners[ i ] is listener:
                del self.listeners[ i ]
                return
        logger.info( "listener {} not registered".format( listener ) )

    ############################
    def querryTaskState( self, taskId ):
        return self.taskServer.taskManager.querryTaskState( taskId )

    ############################
    def pullResources( self, taskId, listFiles ):
        self.resourceServer.addFilesToGet( listFiles, taskId )
        self.getResourcePeers()

    ############################
    def addResourcePeer( self, clientId, addr, port ):
        self.resourceServer.addResourcePeer( clientId, addr, port )

    ############################
    def supportedTask( self, thDictRepr ):
        supported = self.__checkSupportedEnvironment( thDictRepr )
        return supported and self.__checkSupportedVersion( thDictRepr )

    ############################
    def getResDirs( self ):
        dirs = { "computing": self.getComputedFilesDir(),
                 "received": self.getReceivedFilesDir(),
                 "distributed": self.getDistributedFilesDir()
                }
        return dirs

    def getComputedFilesDir( self ):
        return self.taskServer.getTaskComputerRoot()

    def getReceivedFilesDir( self ):
        return self.taskServer.taskManager.getTaskManagerRoot()

    def getDistributedFilesDir( self ):
        return self.resourceServer.getDistributedResourceRoot()

    ############################
    def removeComputedFiles( self ):
        dirManager = DirManager(self.configDesc.rootPath, self.configDesc.clientUid )
        dirManager.clearDir( self.getComputedFilesDir() )

   ############################
    def removeDistributedFiles( self ):
        dirManager = DirManager(self.configDesc.rootPath, self.configDesc.clientUid )
        dirManager.clearDir( self.getDistributedFilesDir() )

   ############################
    def removeReceivedFiles( self ):
        dirManager = DirManager(self.configDesc.rootPath, self.configDesc.clientUid )
        dirManager.clearDir( self.getReceivedFilesDir() )

    ############################
    def __checkSupportedEnvironment( self, thDictRepr ):
        if "environment" not in thDictRepr:
            return False
        if not self.environmentsManager.supported( thDictRepr["environment"] ):
            return False
        return self.environmentsManager.acceptTasks( thDictRepr[ "environment"] )

    #############################
    def __checkSupportedVersion( self, thDictRepr ):
        if "minVersion" not in thDictRepr:
            return True
        try:
            supported =  float( self.configDesc.appVersion ) >= float( thDictRepr[ "minVersion" ] )
            return supported
        except ValueError:
            logger.error(
                "Wrong app version - app version {}, required version {}".format(
                    self.configDesc.appVersion,
                    thDictRepr[ "minVersion" ]
                )
            )
            return False

    ############################
    def getEnvironments( self ):
        return self.environmentsManager.getEnvironments()

    ############################
    def changeAcceptTasksForEnvironment( self, envId, state ):
        self.environmentsManager.changeAcceptTasks( envId, state )

    ############################
    def __doWork(self):
        if self.p2pservice:
            if self.configDesc.sendPings:
                self.p2pservice.pingPeers( self.configDesc.pingsInterval )

            self.p2pservice.syncNetwork()
            self.taskServer.syncNetwork()
            self.resourceServer.syncNetwork()


            if time.time() - self.lastNSSTime > self.configDesc.nodeSnapshotInterval:
                with self.snapshotLock:
                    self.__makeNodeStateSnapshot()
                self.lastNSSTime = time.time()
                for l in self.listeners:
                    l.checkNetworkState()

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
                msg = "{} \n {} ({}%)\n".format( msg, k, v.getProgress() * 100 )
        else:
            msg = "Waiting for tasks...\n"

        peers = self.p2pservice.getPeers()

        msg += "Active peers in network: {}\n".format(len(peers))
        msg += "Budget: {}\n".format( self.budget )
        return msg

    def getAboutInfo( self ):
        return self.configDesc.appName, self.configDesc.appVersion
