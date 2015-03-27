from twisted.internet import task
from threading import Lock

from golem.network.p2p.P2PService import P2PService
from golem.task.TaskServer import TaskServer
from golem.task.TaskManager import TaskManagerEventListener

from golem.core.hostaddress import getHostAddress

from golem.manager.NodeStateSnapshot import NodeStateSnapshot

import time

from golem.AppConfig import AppConfig
#from golem.BankConfig import BankConfig
from golem.Model import Database, Bank
from golem.Message import initMessages
from golem.ClientConfigDescriptor import ClientConfigDescriptor
from golem.environments.EnvironmentsManager import EnvironmentsManager
from golem.resource.ResourceServer import ResourceServer
from golem.resource.DirManager import DirManager
from golem.ranking.Ranking import Ranking, RankingDatabase

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
    p2pSessionTimeout           = cfg.getP2pSessionTimeout()
    taskSessionTimeout          = cfg.getTaskSessionTimeout()
    resourceSessionTimeout      = cfg.getResourceSessionTimeout()

    estimatedPerformance        = cfg.getEstimatedPerformance()
    nodeSnapshotInterval        = cfg.getNodeSnapshotInterval()
    useDistributedResourceManagement = cfg.getUseDistributedResourceManagement()
    requestingTrust             = cfg.getRequestingTrust()
    computingTrust              = cfg.getComputingTrust()

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
    configDesc.p2pSessionTimeout        = p2pSessionTimeout
    configDesc.taskSessionTimeout       = taskSessionTimeout
    configDesc.resourceSessionTimeout   = resourceSessionTimeout

    configDesc.estimatedPerformance     = estimatedPerformance
    configDesc.nodeSnapshotInterval     = nodeSnapshotInterval
    configDesc.maxResultsSendingDelay   = cfg.getMaxResultsSendingDelay()
    configDesc.useDistributedResourceManagement = useDistributedResourceManagement
    configDesc.requestingTrust          = requestingTrust
    configDesc.computingTrust           = computingTrust


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

        self.ranking = Ranking( self, RankingDatabase( self.db ) )
       # self.ranking.start()
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
    def increaseComputingTrust( self, nodeId, trustMod ):
        self.ranking.increaseComputingTrust( nodeId, trustMod )

    ############################
    def decreaseComputingTrust( self, nodeId, trustMod ):
        self.ranking.decreaseComputingTrust( nodeId, trustMod )

    ############################
    def increaseRequesterTrust( self, nodeId, trustMod ):
        self.ranking.increaseRequesterTrust( nodeId, trustMod )

    ############################
    def decreaseRequesterTrust( self, nodeId, trustMod ):
        self.ranking.decreaseRequesterTrust( nodeId, trustMod )

    ############################
    def getNeighboursDegree( self ):
        return self.p2pservice.getPeersDegree()

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
        self.configDesc.seedHostPort = self.__tryChangeToNumber( self.configDesc.seedHostPort, newConfigDesc.seedHostPort,
                                                           toInt = True, name = 'Seed host port' )

        if self.configDesc.rootPath != newConfigDesc.rootPath:
            self.resourceServer.changeResourceDir( newConfigDesc )
        self.configDesc.rootPath = newConfigDesc.rootPath
        self.configDesc.managerPort = self.__tryChangeToNumber(self.configDesc.managerPort, newConfigDesc.managerPort,
                                                               toInt = True, name = 'Manager port')

        self.configDesc.numCores = newConfigDesc.numCores
        self.configDesc.estimatedPerformance = newConfigDesc.estimatedPerformance
        self.configDesc.maxResourceSize = newConfigDesc.maxResourceSize
        self.configDesc.maxMemorySize   = newConfigDesc.maxMemorySize

        self.configDesc.optNumPeers = self.__tryChangeToNumber(self.configDesc.optNumPeers, newConfigDesc.optNumPeers,
                                                              toInt = True, name='Opt peers number')

        self.configDesc.useDistributedResourceManagement = newConfigDesc.useDistributedResourceManagement

        self.configDesc.distResNum = self.__tryChangeToNumber( self.configDesc.distResNum,
                                                                      newConfigDesc.distResNum,
                                                                      toInt = True,
                                                                      name = 'Distributed resource number')

        self.configDesc.useWaitingForTaskTimeout = newConfigDesc.useWaitingForTaskTimeout

        self.configDesc.waitingForTaskTimeout = self.__tryChangeToNumber( self.configDesc.waitingForTaskTimeout,
                                                                          newConfigDesc.waitingForTaskTimeout,
                                                                          toFloat = True,
                                                                          name = "Waiting for task timeout")

        self.configDesc.p2pSessionTimeout = self.__tryChangeToNumber( self.configDesc.p2pSessionTimeout,
                                                                      newConfigDesc.p2pSessionTimeout,
                                                                      toInt = True,
                                                                      name = 'P2p session timeout')

        self.configDesc.taskSessionTimeout = self.__tryChangeToNumber( self.configDesc.taskSessionTimeout,
                                                                      newConfigDesc.taskSessionTimeout,
                                                                      toInt = True,
                                                                      name = 'Task session timeout')

        self.configDesc.resourceSessionTimeout = self.__tryChangeToNumber( self.configDesc.resourceSessionTimeout,
                                                                      newConfigDesc.resourceSessionTimeout,
                                                                      toInt = True,
                                                                      name = 'Resource session timeout')


        self.configDesc.sendPings = newConfigDesc.sendPings


        self.configDesc.pingsInterval = self.__tryChangeToNumber( self.configDesc.pingsInterval,
                                                                  newConfigDesc.pingsInterval,
                                                                  toFloat = True,
                                                                  name = 'Ping interval')


        self.configDesc.gettingPeersInterval = self.__tryChangeToNumber( self.configDesc.gettingPeersInterval,
                                                                           newConfigDesc.gettingPeersInterval,
                                                                           toFloat = True,
                                                                           name = "Getting peers interval")


        self.configDesc.gettingTasksInterval = self.__tryChangeToNumber( self.configDesc.gettingTasksInterval,
                                                                           newConfigDesc.gettingTasksInterval,
                                                                           toFloat = True,
                                                                           name = "Getting tasks interval")

        self.configDesc.nodeSnapshotInterval = self.__tryChangeToNumber( self.configDesc.nodeSnapshotInterval,
                                                                      newConfigDesc.nodeSnapshotInterval,
                                                                      toFloat = True,
                                                                      name = "Node snapshot interval")

        self.configDesc.maxResultsSendingDelay = self.__tryChangeToNumber( self.configDesc.maxResultsSendingDelay,
                                                                      newConfigDesc.maxResultsSendingDelay,
                                                                      toFloat = True,
                                                                      name = "Max result sending delay")


        self.configDesc.computingTrust = self.__tryChangeToNumber( self.configDesc.computingTrust,
                                                                      newConfigDesc.computingTrust,
                                                                      toFloat = True,
                                                                      name = "Minimum trust for computing node")


        self.configDesc.requestingTrust = self.__tryChangeToNumber( self.configDesc.requestingTrust,
                                                                      newConfigDesc.requestingTrust,
                                                                      toFloat = True,
                                                                      name = "Minimum trust for requesting node")

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
    def getEnvironments( self ):
        return self.environmentsManager.getEnvironments()

    ############################
    def changeAcceptTasksForEnvironment( self, envId, state ):
        self.environmentsManager.changeAcceptTasks( envId, state )

    ############################
    def getComputingTrust(self, nodeId):
        return self.ranking.getComputingTrust( nodeId )

    ############################
    def sendGossip(self, gossip, sendTo):
        return self.p2pservice.sendGossip( gossip, sendTo )

    ############################
    def sendStopGossip(self):
        return self.p2pservice.sendStopGossip()

    ############################
    def getRequestingTrust(self, nodeId):
        return self.ranking.getRequestingTrust( nodeId )

    ############################
    def collectGossip(self):
        return self.p2pservice.popGossip()

    ############################
    def collectStoppedPeers(self):
        return self.p2pservice.popStopGossipFromPeers()

    ############################
    def __tryChangeToNumber(self, oldValue, newValue, toInt = False, toFloat = False, name="Config"):
        try:
            if toInt:
                newValue = int( newValue )
            elif toFloat:
                newValue = float( newValue )
        except ValueError:
            logger.warning("{} value '{}' is not a number".format( name, newValue ))
            newValue = oldValue
        return newValue

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
            tasksNum                = len( self.taskServer.taskKeeper.taskHeaders )
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
