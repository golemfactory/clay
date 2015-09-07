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

    opt_num_peers     = cfg.getOptimalPeerNum()
    manager_address  = cfg.getManagerAddress()
    manager_port     = cfg.getManagerListenPort()
    start_port       = cfg.getStartPort()
    end_port         = cfg.getEndPort()
    seed_host        = cfg.getSeedHost()
    seed_host_port    = cfg.getSeedHostPort()
    send_pings       = cfg.getSendPings()
    pings_interval   = cfg.getPingsInterval()
    client_uid       = cfg.getClientUid()
    add_tasks        = cfg.getAddTasks()
    root_path        = cfg.getRootPath()
    num_cores        = cfg.getNumCores()
    max_resource_size = cfg.getMaxResourceSize()
    max_memory_size   = cfg.getMaxMemorySize()
    dist_res_num      = cfg.getDistributedResNum()
    appName         = cfg.getAppName()
    appVersion      = cfg.getAppVersion()
    plugin_port      = cfg.getPluginPort()

    getting_peers_interval        = cfg.getGettingPeersInterval()
    getting_tasks_interval        = cfg.getGettingTasksInterval()
    task_request_interval         = cfg.getTaskRequestInterval()
    use_waiting_for_task_timeout    = cfg.getUseWaitingForTaskTimeout()
    waiting_for_task_timeout       = cfg.getWaitingForTaskTimeout()
    p2p_session_timeout           = cfg.getP2pSessionTimeout()
    task_session_timeout          = cfg.getTaskSessionTimeout()
    resource_session_timeout      = cfg.getResourceSessionTimeout()

    estimated_performance        = cfg.getEstimatedPerformance()
    node_snapshot_interval        = cfg.getNodeSnapshotInterval()
    use_distributed_resource_management = cfg.getUseDistributedResourceManagement()
    requesting_trust             = cfg.getRequestingTrust()
    computing_trust              = cfg.getComputingTrust()

    eth_account                  = cfg.getEthAccount()
    use_ipv6                      = cfg.getUseIp6()

    config_desc = ClientConfigDescriptor()

    config_desc.client_uid        = client_uid
    config_desc.start_port        = start_port
    config_desc.end_port          = end_port
    config_desc.manager_address   = manager_address
    config_desc.manager_port      = manager_port
    config_desc.opt_num_peers      = opt_num_peers
    config_desc.send_pings        = send_pings
    config_desc.pings_interval    = pings_interval
    config_desc.add_tasks         = add_tasks
    config_desc.client_version   = 1
    config_desc.root_path         = root_path
    config_desc.num_cores         = num_cores
    config_desc.max_resource_size  = max_resource_size
    config_desc.max_memory_size    = max_memory_size
    config_desc.dist_res_num       = dist_res_num

    config_desc.seed_host               = seed_host
    config_desc.seed_host_port           = seed_host_port

    config_desc.appVersion             = appVersion
    config_desc.appName                = appName

    config_desc.plugin_port               = plugin_port
    config_desc.getting_peers_interval     = getting_peers_interval
    config_desc.getting_tasks_interval     = getting_tasks_interval
    config_desc.task_request_interval      = task_request_interval
    config_desc.use_waiting_for_task_timeout = use_waiting_for_task_timeout
    config_desc.waiting_for_task_timeout    = waiting_for_task_timeout
    config_desc.p2p_session_timeout        = p2p_session_timeout
    config_desc.task_session_timeout       = task_session_timeout
    config_desc.resource_session_timeout   = resource_session_timeout

    config_desc.estimated_performance     = estimated_performance
    config_desc.node_snapshot_interval     = node_snapshot_interval
    config_desc.max_results_sending_delay   = cfg.getMaxResultsSendingDelay()
    config_desc.use_distributed_resource_management = use_distributed_resource_management
    config_desc.requesting_trust          = requesting_trust
    config_desc.computing_trust           = computing_trust

    config_desc.eth_account               = eth_account
    config_desc.useIp6                   = use_ipv6


    logger.info("Adding tasks {}".format(add_tasks))
    logger.info("Creating public client interface with uuid: {}".format(client_uid))
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
    def __init__(self, config_desc, root_path = "", config = ""):
        self.config_desc     = config_desc
        self.keys_auth       = EllipticalKeysAuth(config_desc.client_uid)
        self.configApprover = ConfigApprover(config_desc)

        #NETWORK
        self.node = Node(self.config_desc.client_uid, self.keys_auth.get_key_id())
        self.node.collectNetworkInfo(self.config_desc.seed_host, use_ipv6=self.config_desc.useIp6)
        logger.debug("Is super node? {}".format(self.node.isSuperNode()))
        self.p2pservice = None

        self.task_server = None
        self.taskAdderServer = None
        self.lastNSSTime = time.time()

        self.lastNodeStateSnapshot = None

        self.nodesManagerClient = None

        self.doWorkTask = task.LoopingCall(self.__doWork)
        self.doWorkTask.start(0.1, False)

        self.listeners = []

        self.root_path = root_path
        self.cfg = config
        self.sendSnapshot = False
        self.snapshotLock = Lock()

        self.db = Database()
        self.db.checkNode(self.config_desc.client_uid)

        self.ranking = Ranking(self, RankingDatabase(self.db))

        self.transactionSystem = EthereumTransactionSystem(self.config_desc.client_uid, self.config_desc.eth_account)

        self.environmentsManager = EnvironmentsManager()

        self.resource_server = None
        self.resource_port   = 0
        self.lastGetResourcePeersTime  = time.time()
        self.getResourcePeersInterval = 5.0

    ############################
    def startNetwork(self):
        logger.info("Starting network ...")

        logger.info("Starting p2p server ...")
        self.p2pservice = P2PService(self.node, self.config_desc, self.keys_auth)
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
        if self.config_desc.use_distributed_resource_management:
            self.get_resource_peers()
            resFiles = self.resource_server.add_files_to_send(task.taskResources, task.header.taskId, self.config_desc.dist_res_num)
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
    def setResourcePort (self, resource_port):
        self.resource_port = resource_port
        self.p2pservice.set_resource_peer(self.node.prvAddr, self.resource_port)

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
        return self.config_desc.client_uid

    ############################
    def getRootPath(self):
        return self.config_desc.root_path

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
    def change_config(self, new_config_desc):
        self.config_desc = self.configApprover.change_config(new_config_desc)
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
        dirManager = DirManager(self.config_desc.root_path, self.config_desc.client_uid)
        dirManager.clearDir(self.getComputedFilesDir())

   ############################
    def removeDistributedFiles(self):
        dirManager = DirManager(self.config_desc.root_path, self.config_desc.client_uid)
        dirManager.clearDir(self.getDistributedFilesDir())

   ############################
    def removeReceivedFiles(self):
        dirManager = DirManager(self.config_desc.root_path, self.config_desc.client_uid)
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
        return self.config_desc.plugin_port

    ############################
    def getEthAccount(self):
        return self.config_desc.eth_account

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
            if self.config_desc.send_pings:
                self.p2pservice.ping_peers(self.config_desc.pings_interval)

            self.p2pservice.sync_network()
            self.task_server.sync_network()
            self.resource_server.sync_network()
            self.ranking.sync_network()


            if time.time() - self.lastNSSTime > self.config_desc.node_snapshot_interval:
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
                                                           ,    self.config_desc.client_uid
                                                           ,    peersNum
                                                           ,    tasksNum
                                                           ,    self.p2pservice.node.pubAddr
                                                           ,    self.p2pservice.node.pubPort
                                                           ,    lastNetworkMessages
                                                           ,    lastTaskMessages
                                                           ,    remoteTasksProgresses  
                                                           ,    localTasksProgresses)
        else:
            self.lastNodeStateSnapshot = NodeStateSnapshot(self.config_desc.client_uid, peersNum)


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
