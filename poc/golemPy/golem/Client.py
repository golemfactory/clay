import time
import datetime
import logging

from twisted.internet import task
from threading import Lock

from golem.network.p2p.P2PService import P2PService
from golem.network.p2p.Node import Node
from golem.task.TaskServer import TaskServer
from golem.task.TaskManager import TaskManagerEventListener

from golem.core.keys_auth import EllipticalKeysAuth

from golem.manager.NodeStateSnapshot import NodeStateSnapshot

from golem.AppConfig import AppConfig

from golem.Model import Database
from golem.network.transport.message import init_messages
from golem.ClientConfigDescriptor import ClientConfigDescriptor, ConfigApprover
from golem.environments.EnvironmentsManager import EnvironmentsManager
from golem.resource.ResourceServer import ResourceServer
from golem.resource.DirManager import DirManager
from golem.ranking.Ranking import Ranking, RankingDatabase

from golem.transactions.Ethereum.EthereumTransactionSystem import EthereumTransactionSystem

logger = logging.getLogger(__name__)

def emptyAddNodes(*args):
    pass

def startClient():
    init_messages()

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
    pluginPort      = cfg.getPluginPort()

    gettingPeersInterval        = cfg.getGettingPeersInterval()
    gettingTasksInterval        = cfg.getGettingTasksInterval()
    taskRequestInterval         = cfg.getTaskRequestInterval()
    useWaitingForTaskTimeout    = cfg.getUseWaitingForTaskTimeout()
    waitingForTaskTimeout       = cfg.getWaitingForTaskTimeout()
    p2pSessionTimeout           = cfg.getP2pSessionTimeout()
    task_sessionTimeout          = cfg.getTaskSessionTimeout()
    resourceSessionTimeout      = cfg.getResourceSessionTimeout()

    estimatedPerformance        = cfg.getEstimatedPerformance()
    nodeSnapshotInterval        = cfg.getNodeSnapshotInterval()
    useDistributedResourceManagement = cfg.getUseDistributedResourceManagement()
    requestingTrust             = cfg.getRequestingTrust()
    computingTrust              = cfg.getComputingTrust()

    ethAccount                  = cfg.getEthAccount()
    use_ipv6                      = cfg.getUseIp6()

    config_desc = ClientConfigDescriptor()

    config_desc.clientUid        = clientUid
    config_desc.startPort        = startPort
    config_desc.endPort          = endPort
    config_desc.managerAddress   = managerAddress
    config_desc.managerPort      = managerPort
    config_desc.optNumPeers      = optNumPeers
    config_desc.sendPings        = sendPings
    config_desc.pingsInterval    = pingsInterval
    config_desc.addTasks         = addTasks
    config_desc.clientVersion    = 1
    config_desc.rootPath         = rootPath
    config_desc.numCores         = numCores
    config_desc.maxResourceSize  = maxResourceSize
    config_desc.maxMemorySize    = maxMemorySize
    config_desc.distResNum       = distResNum

    config_desc.seedHost               = seedHost
    config_desc.seedHostPort           = seedHostPort

    config_desc.appVersion             = appVersion
    config_desc.appName                = appName

    config_desc.pluginPort               = pluginPort
    config_desc.gettingPeersInterval     = gettingPeersInterval
    config_desc.gettingTasksInterval     = gettingTasksInterval
    config_desc.taskRequestInterval      = taskRequestInterval
    config_desc.useWaitingForTaskTimeout = useWaitingForTaskTimeout
    config_desc.waitingForTaskTimeout    = waitingForTaskTimeout
    config_desc.p2pSessionTimeout        = p2pSessionTimeout
    config_desc.taskSessionTimeout       = task_sessionTimeout
    config_desc.resourceSessionTimeout   = resourceSessionTimeout

    config_desc.estimatedPerformance     = estimatedPerformance
    config_desc.nodeSnapshotInterval     = nodeSnapshotInterval
    config_desc.maxResultsSendingDelay   = cfg.getMaxResultsSendingDelay()
    config_desc.useDistributedResourceManagement = useDistributedResourceManagement
    config_desc.requestingTrust          = requestingTrust
    config_desc.computingTrust           = computingTrust

    config_desc.ethAccount               = ethAccount
    config_desc.useIp6                   = use_ipv6


    logger.info("Adding tasks {}".format(addTasks))
    logger.info("Creating public client interface with uuid: {}".format(clientUid))
    c = Client(config_desc, config = cfg)

    logger.info("Starting all asynchronous services")
    c.startNetwork()

    return c

class GolemClientEventListener:
    ############################
    def __init__(self):
        pass

    ############################
    def taskUpdated(self, taskId):
        pass

    ############################
    def networkConnected(self):
        pass


class ClientTaskManagerEventListener(TaskManagerEventListener):
    #############################
    def __init__(self, client):
        self.client = client

    #######################
    def taskStatusUpdated(self, taskId):
        for l in self.client.listeners:
            l.taskUpdated(taskId)

    #######################
    def taskFinished(self, taskId):
        self.client.taskFinished(taskId)

class Client:

    ############################
    def __init__(self, config_desc, rootPath = "", config = ""):
        self.config_desc     = config_desc
        self.keys_auth       = EllipticalKeysAuth(config_desc.clientUid)
        self.configApprover = ConfigApprover(config_desc)

        #NETWORK
        self.node = Node(self.config_desc.clientUid, self.keys_auth.get_key_id())
        self.node.collectNetworkInfo(self.config_desc.seedHost, use_ipv6=self.config_desc.useIp6)
        logger.debug("Is super node? {}".format(self.node.isSuperNode()))
        self.p2service = None

        self.task_server = None
        self.taskAdderServer = None
        self.lastNSSTime = time.time()

        self.lastNodeStateSnapshot = None

        self.nodesManagerClient = None

        self.doWorkTask = task.LoopingCall(self.__doWork)
        self.doWorkTask.start(0.1, False)

        self.listeners = []

        self.rootPath = rootPath
        self.cfg = config
        self.sendSnapshot = False
        self.snapshotLock = Lock()

        self.db = Database()
        self.db.checkNode(self.config_desc.clientUid)

        self.ranking = Ranking(self, RankingDatabase(self.db))

        self.transactionSystem = EthereumTransactionSystem(self.config_desc.clientUid, self.config_desc.ethAccount)

        self.environmentsManager = EnvironmentsManager()

        self.resource_server = None
        self.resourcePort   = 0
        self.lastGetResourcePeersTime  = time.time()
        self.getResourcePeersInterval = 5.0

    ############################
    def startNetwork(self):
        logger.info("Starting network ...")

        logger.info("Starting p2p server ...")
        self.p2pservice = P2PService(self.node, self.config_desc, self.keys_auth, use_ipv6=self.config_desc.useIp6)
        time.sleep(1.0)

        logger.info("Starting resource server...")
        self.resource_server = ResourceServer(self.config_desc, self.keys_auth, self, use_ipv6=self.config_desc.useIp6)
        self.resource_server.start_accepting()
        time.sleep(1.0)
        self.p2pservice.set_resource_server(self.resource_server)

        logger.info("Starting task server ...")
        self.task_server = TaskServer(self.node, self.config_desc, self.keys_auth, self,
                                     use_ipv6=self.config_desc.useIp6)
        self.task_server.start_accepting()

        self.p2pservice.set_task_server(self.task_server)

        time.sleep(0.5)
        self.task_server.task_manager.registerListener(ClientTaskManagerEventListener(self))

    ############################
    def runAddTaskServer(self):
        from PluginServer import startTaskAdderServer
        from multiprocessing import Process, freeze_support
        freeze_support()
        self.taskAdderServer = Process(target = startTaskAdderServer, args=(self.getPluginPort(),))
        self.taskAdderServer.start()

    ############################
    def quit(self):
        if self.taskAdderServer:
            self.taskAdderServer.terminate()

    ############################
    def stopNetwork(self):
        #FIXME: Pewnie cos tu trzeba jeszcze dodac. Zamykanie serwera i wysylanie DisconnectPackege
        self.p2pservice         = None
        self.task_server         = None
        self.nodesManagerClient = None

    ############################
    def enqueueNewTask(self, task):
        self.task_server.task_manager.addNewTask(task)
        if self.config_desc.useDistributedResourceManagement:
            self.get_resource_peers()
            resFiles = self.resource_server.add_files_to_send(task.taskResources, task.header.taskId, self.config_desc.distResNum)
            task.setResFiles(resFiles)

    ############################
    def get_resource_peers(self):
        self.p2pservice.send_get_resource_peers()

    ############################
    def taskResourcesSend(self, taskId):
        self.task_server.task_manager.resourcesSend(taskId)

    ############################
    def taskResourcesCollected(self, taskId):
        self.task_server.task_computer.taskResourceCollected(taskId)

    ############################
    def setResourcePort (self, resourcePort):
        self.resourcePort = resourcePort
        self.p2pservice.set_resource_peer(self.node.prvAddr, self.resourcePort)

    ############################
    def abortTask(self, taskId):
        self.task_server.task_manager.abortTask(taskId)

    ############################
    def restartTask(self, taskId):
        self.task_server.task_manager.restartTask(taskId)

    ############################
    def restartSubtask(self, subtaskId):
        self.task_server.task_manager.restartSubtask(subtaskId)

    ############################
    def pauseTask(self, taskId):
        self.task_server.task_manager.pauseTask(taskId)

    ############################
    def resumeTask(self, taskId):
        self.task_server.task_manager.resumeTask(taskId)

    ############################
    def deleteTask(self, taskId):
        self.task_server.remove_task_header(taskId)
        self.task_server.task_manager.deleteTask(taskId)

    ############################
    def getId(self):
        return self.config_desc.clientUid

    ############################
    def getRootPath(self):
        return self.config_desc.rootPath

    ############################
    def increaseTrust(self, nodeId, stat, mod = 1.0):
        self.ranking.increaseTrust(nodeId, stat, mod)

    ############################
    def decreaseTrust(self, nodeId, stat, mod = 1.0):
        self.ranking.decreaseTrust(nodeId, stat, mod)

    ############################
    def getNeighboursDegree(self):
        return self.p2pservice.get_peers_degree()

    ############################
    def getSuggestedAddr(self, keyId):
        return self.p2pservice.suggested_address.get(keyId)

    ############################
    def want_to_start_task_session(self, keyId, nodeId, conn_id):
        self.p2pservice.want_to_start_task_session(keyId, nodeId, conn_id)

    ############################
    def inform_about_task_nat_hole(self, keyId, rvKeyId, addr, port, ansConnId):
        self.p2pservice.inform_about_task_nat_hole(keyId, rvKeyId, addr, port, ansConnId)

    ############################
    def inform_about_nat_traverse_failure(self, keyId, resKeyId, conn_id):
        self.p2pservice.inform_about_nat_traverse_failure(keyId, resKeyId, conn_id)

    #TRANSACTION SYSTEM OPERATIONS
    ############################
    def accept_result(self, taskId, subtaskId, priceMod, accountInfo):
        self.transactionSystem.addPaymentInfo(taskId, subtaskId, priceMod, accountInfo)

    ############################
    def taskRewardPaid(self, taskId, price):
        return self.transactionSystem.taskRewardPaid(taskId, price)

    ############################
    def taskRewardPayment_failure(self, taskId, price):
        return self.transactionSystem.taskRewardPayment_failure(taskId, price)

    ############################
    def global_pay_for_task(self, taskId, payments):
        self.transactionSystem.global_pay_for_task(taskId, payments)

    ############################
    def getReward(self, reward):
        self.transactionSystem.getReward(reward)

    ############################
    def getNewPaymentsTasks(self):
        return self.transactionSystem.getNewPaymentsTasks()

    #CLIENT CONFIGURATION
    ############################
    def registerListener(self, listener):
        assert isinstance(listener, GolemClientEventListener)
        self.listeners.append(listener)

    ############################
    def change_config(self, newConfigDesc):
        self.config_desc = self.configApprover.change_config(newConfigDesc)
        self.cfg.change_config(self.config_desc)
        self.resource_server.change_resource_dir(self.config_desc)
        self.p2pservice.change_config(self.config_desc)
        self.task_server.change_config(self.config_desc)

    ############################
    def registerNodesManagerClient(self, nodesManagerClient):
        self.nodesManagerClient = nodesManagerClient

    ############################
    def change_timeouts(self, taskId, fullTaskTimeout, subtaskTimeout, minSubtaskTime):
        self.task_server.change_timeouts(taskId, fullTaskTimeout, subtaskTimeout, minSubtaskTime)

    ############################
    def unregisterListener(self, listener):
        assert isinstance(listener, GolemClientEventListener)
        for i in range(len(self.listeners)):
            if self.listeners[i] is listener:
                del self.listeners[ i]
                return
        logger.info("listener {} not registered".format(listener))

    ############################
    def querryTaskState(self, taskId):
        return self.task_server.task_manager.querryTaskState(taskId)

    ############################
    def pull_resources(self, taskId, listFiles):
        self.resource_server.add_files_to_get(listFiles, taskId)
        self.get_resource_peers()

    ############################
    def add_resource_peer(self, client_id, addr, port, keyId, node_info):
        self.resource_server.add_resource_peer(client_id, addr, port, keyId, node_info)

    ############################
    def supportedTask(self, th_dict_repr):
        supported = self.__checkSupportedEnvironment(th_dict_repr)
        return supported and self.__checkSupportedVersion(th_dict_repr)

    ############################
    def getResDirs(self):
        dirs = { "computing": self.getComputedFilesDir(),
                 "received": self.getReceivedFilesDir(),
                 "distributed": self.getDistributedFilesDir()
                }
        return dirs

    def getComputedFilesDir(self):
        return self.task_server.get_task_computer_root()

    def getReceivedFilesDir(self):
        return self.task_server.task_manager.getTaskManagerRoot()

    def getDistributedFilesDir(self):
        return self.resource_server.get_distributed_resource_root()

    ############################
    def removeComputedFiles(self):
        dirManager = DirManager(self.config_desc.rootPath, self.config_desc.clientUid)
        dirManager.clearDir(self.getComputedFilesDir())

   ############################
    def removeDistributedFiles(self):
        dirManager = DirManager(self.config_desc.rootPath, self.config_desc.clientUid)
        dirManager.clearDir(self.getDistributedFilesDir())

   ############################
    def removeReceivedFiles(self):
        dirManager = DirManager(self.config_desc.rootPath, self.config_desc.clientUid)
        dirManager.clearDir(self.getReceivedFilesDir())

    ############################
    def getEnvironments(self):
        return self.environmentsManager.getEnvironments()

    ############################
    def changeAcceptTasksForEnvironment(self, envId, state):
        self.environmentsManager.changeAcceptTasks(envId, state)

    ############################
    def get_computing_trust(self, nodeId):
        return self.ranking.get_computing_trust(nodeId)

    ############################
    def send_gossip(self, gossip, send_to):
        return self.p2pservice.send_gossip(gossip, send_to)

    ############################
    def send_stop_gossip(self):
        return self.p2pservice.send_stop_gossip()

    ############################
    def getRequestingTrust(self, nodeId):
        return self.ranking.getRequestingTrust(nodeId)

    ############################
    def collectGossip(self):
        return self.p2pservice.pop_gossip()

    ############################
    def collectStoppedPeers(self):
        return self.p2pservice.pop_stop_gossip_form_peers()

    ############################
    def collectNeighboursLocRanks(self):
        return self.p2pservice.pop_neighbours_loc_ranks()

    ############################
    def push_local_rank(self, nodeId, locRank):
        self.p2pservice.push_local_rank(nodeId, locRank)

    ############################
    def getPluginPort(self):
        return self.config_desc.pluginPort

    ############################
    def getEthAccount(self):
        return self.config_desc.ethAccount

    ############################
    def taskFinished(self, taskId):
        self.transactionSystem.taskFinished(taskId)

    ############################
    def __tryChangeToNumber(self, oldValue, newValue, toInt = False, toFloat = False, name="Config"):
        try:
            if toInt:
                newValue = int(newValue)
            elif toFloat:
                newValue = float(newValue)
        except ValueError:
            logger.warning("{} value '{}' is not a number".format(name, newValue))
            newValue = oldValue
        return newValue

    ############################
    def __checkSupportedEnvironment(self, th_dict_repr):
        env = th_dict_repr.get("environment")
        if not env:
            return False
        if not self.environmentsManager.supported(env):
            return False
        return self.environmentsManager.acceptTasks(env)

    #############################
    def __checkSupportedVersion(self, th_dict_repr):
        minV = th_dict_repr.get("minVersion")
        if not minV:
            return True
        try:
            supported =  float(self.config_desc.appVersion) >= float(minV)
            return supported
        except ValueError:
            logger.error(
                "Wrong app version - app version {}, required version {}".format(
                    self.config_desc.appVersion,
                    minV
              )
          )
            return False

    ############################
    def __doWork(self):
        if self.p2pservice:
            if self.config_desc.sendPings:
                self.p2pservice.ping_peers(self.config_desc.pingsInterval)

            self.p2pservice.sync_network()
            self.task_server.sync_network()
            self.resource_server.sync_network()
            self.ranking.sync_network()


            if time.time() - self.lastNSSTime > self.config_desc.nodeSnapshotInterval:
                with self.snapshotLock:
                    self.__makeNodeStateSnapshot()
                self.lastNSSTime = time.time()
                for l in self.listeners:
                    l.checkNetworkState()

                #self.managerServer.sendStateMessage(self.lastNodeStateSnapshot)

    ############################
    def __makeNodeStateSnapshot(self, isRunning = True):

        peersNum            = len(self.p2pservice.peers)
        lastNetworkMessages = self.p2pservice.get_last_messages()

        if self.task_server:
            tasksNum                = len(self.task_server.task_keeper.taskHeaders)
            remoteTasksProgresses   = self.task_server.task_computer.getProgresses()
            localTasksProgresses    = self.task_server.task_manager.getProgresses()
            lastTaskMessages        = self.task_server.get_last_messages()
            self.lastNodeStateSnapshot = NodeStateSnapshot(   isRunning
                                                           ,    self.config_desc.clientUid
                                                           ,    peersNum
                                                           ,    tasksNum
                                                           ,    self.p2pservice.node.pubAddr
                                                           ,    self.p2pservice.node.pubPort
                                                           ,    lastNetworkMessages
                                                           ,    lastTaskMessages
                                                           ,    remoteTasksProgresses  
                                                           ,    localTasksProgresses)
        else:
            self.lastNodeStateSnapshot = NodeStateSnapshot(self.config_desc.clientUid, peersNum)


        if self.nodesManagerClient:
            self.nodesManagerClient.sendClientStateSnapshot(self.lastNodeStateSnapshot)

    def getStatus(self):
        progress = self.task_server.task_computer.getProgresses()
        if len(progress) > 0:
            msg =  "Counting {} subtask(s):".format(len(progress))
            for k, v in progress.iteritems():
                msg = "{} \n {} ({}%)\n".format(msg, k, v.getProgress() * 100)
        else:
            msg = "Waiting for tasks...\n"

        peers = self.p2pservice.get_peers()

        msg += "Active peers in network: {}\n".format(len(peers))
        msg += "Budget: {}\n".format(self.transactionSystem.budget)
        return msg

    def getAboutInfo(self):
        return self.config_desc.appName, self.config_desc.appVersion
