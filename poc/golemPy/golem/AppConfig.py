import sys
sys.path.append('core')
import os
import logging

from golem.core.simpleconfig import SimpleConfig, ConfigEntry
from golem.core.simpleenv import SimpleEnv
from golem.core.prochelper import ProcessService
from ClientConfigDescriptor import  ClientConfigDescriptor

CONFIG_FILENAME = "app_cfg.ini"
ESTM_FILENAME = "minilight.ini"
MANAGER_PORT = 20301
MANAGER_ADDRESS = "127.0.0.1"
ESTIMATED_DEFAULT = 2220.0
START_PORT = 40102
END_PORT = 60102
OPTIMAL_PEER_NUM = 10
MAX_RESOURCE_SIZE = 250 * 1024
MAX_MEMORY_SIZE = 250 * 1024
DISTRIBUTED_RES_NUM = 2
APP_NAME = "Golem LAN Renderer"
APP_VERSION = "1.021"

class CommonConfig:

    ##############################
    def __init__(self,
                  section = "Common",
                  managerAddress = MANAGER_ADDRESS,
                  managerPort = MANAGER_PORT,
                  startPort = START_PORT,
                  endPort = END_PORT,
                  optimalPeerNum = OPTIMAL_PEER_NUM,
                  distributedResNum = DISTRIBUTED_RES_NUM,
                  appName = APP_NAME,
                  appVersion = APP_VERSION):

        self._section = section

        ConfigEntry.create_property(section, "optimal peer num",    optimalPeerNum,    self, "OptimalPeerNum")
        ConfigEntry.create_property(section, "start port",          startPort, self, "StartPort")
        ConfigEntry.create_property(section, "end port",            endPort, self, "EndPort")
        ConfigEntry.create_property(section, "manager address", managerAddress, self, "ManagerAddress")
        ConfigEntry.create_property(section, "manager listen port", managerPort, self, "ManagerListenPort")
        ConfigEntry.create_property(section, "distributed res num", distributedResNum, self, "DistributedResNum")
        ConfigEntry.create_property(section, "application name", appName, self, "AppName")
        ConfigEntry.create_property(section, "application version", appVersion, self, "AppVersion")

    ##############################
    def section(self):
        return self._section


class NodeConfig:

    @classmethod
    def readEstimatedPerformance(cls):
        estmFile = SimpleEnv.env_file_name(ESTM_FILENAME)
        res = 0
        if os.path.isfile(estmFile):
            try:
                with open(estmFile, 'r') as file:
                    res = "{0:.1f}".format(float(file.read()))
            except:
                return 0
        return res

    SEND_PINGS = 1
    PINGS_INTERVALS = 120
    GETTING_PEERS_INTERVAL = 4.0
    GETTING_TASKS_INTERVAL = 4.0
    TASK_REQUEST_INTERVAL = 5.0
    USE_WAITING_FOR_TASK_TIMEOUT = 0
    WAITING_FOR_TASK_TIMEOUT = 36000
    NODE_SNAPSHOT_INTERVAL = 4.0
    ADD_TASKS = 0
    MAX_SENDING_DELAY = 360
    USE_DISTRIBUTED_RESOURCE_MANAGEMENT = 1
    DEFAULT_ROOT_PATH = os.environ.get('GOLEM')
    REQUESTING_TRUST = -1.0
    COMPUTING_TRUST = -1.0
    P2P_SESSION_TIMEOUT = 240
    TASK_SESSION_TIMEOUT = 900
    RESOURCE_SESSION_TIMEOUT = 600
    PLUGIN_PORT = 1111
    ETH_ACCOUNT_NAME = ""
    USE_IP6 = 0


    ##############################
    def __init__(self, nodeId, seedHost = "", seedPort = 0, rootPath = DEFAULT_ROOT_PATH, numCores = 4,
                  maxResourceSize = MAX_RESOURCE_SIZE, maxMemorySize = MAX_MEMORY_SIZE,
                  sendPings = SEND_PINGS, pingsInterval = PINGS_INTERVALS,
                  gettingPeersInterval = GETTING_PEERS_INTERVAL, gettingTasksInterval = GETTING_TASKS_INTERVAL,
                  taskRequestInterval = TASK_REQUEST_INTERVAL, useWaitingForTaskTimeout = USE_WAITING_FOR_TASK_TIMEOUT,
                  waitingForTaskTimeout = WAITING_FOR_TASK_TIMEOUT, nodesSnapshotInterval = NODE_SNAPSHOT_INTERVAL,
                  addTasks = ADD_TASKS, maxSendingDelay = MAX_SENDING_DELAY,
                  requestingTrust = REQUESTING_TRUST, computingTrust = COMPUTING_TRUST,
                  useDistributedResourceManagement = USE_DISTRIBUTED_RESOURCE_MANAGEMENT,
                  p2pSessionTimeout = P2P_SESSION_TIMEOUT, taskSessionTimeout = TASK_SESSION_TIMEOUT,
                  resourceSessionTimeout = RESOURCE_SESSION_TIMEOUT, pluginPort = PLUGIN_PORT,
                  ethAccount = ETH_ACCOUNT_NAME, useIp6 = USE_IP6):
        self._section = "Node {}".format(nodeId)

        estimated = NodeConfig.readEstimatedPerformance()
        if estimated == 0:
            estimated = ESTIMATED_DEFAULT

        ConfigEntry.create_property(self.section(), "seed host", seedHost, self, "SeedHost")
        ConfigEntry.create_property(self.section(), "seed host port", seedPort, self, "SeedHostPort")
        ConfigEntry.create_property(self.section(), "resource root path", rootPath, self, "RootPath")
        ConfigEntry.create_property(self.section(), "send pings", sendPings, self, "SendPings")
        ConfigEntry.create_property(self.section(), "pings interval", pingsInterval, self, "PingsInterval")
        ConfigEntry.create_property(self.section(), "client UUID", u"",   self, "ClientUid")
        ConfigEntry.create_property(self.section(), "getting peers interval",gettingPeersInterval, self, "GettingPeersInterval")
        ConfigEntry.create_property(self.section(), "getting tasks interval", gettingTasksInterval, self, "GettingTasksInterval")
        ConfigEntry.create_property(self.section(), "task request interval", taskRequestInterval, self, "TaskRequestInterval")
        ConfigEntry.create_property(self.section(), "use waiting for task timeout", useWaitingForTaskTimeout, self, "UseWaitingForTaskTimeout")
        ConfigEntry.create_property(self.section(), "waiting for task timeout", waitingForTaskTimeout, self, "WaitingForTaskTimeout")
        ConfigEntry.create_property(self.section(), "estimated perfomance", estimated,  self, "EstimatedPerformance")
        ConfigEntry.create_property(self.section(), "node snapshot interval", nodesSnapshotInterval,  self, "NodeSnapshotInterval")
        ConfigEntry.create_property(self.section(), "add tasks", addTasks, self, "AddTasks")
        ConfigEntry.create_property(self.section(), "maximum delay for sending task results", maxSendingDelay,  self, "MaxResultsSendingDelay")
        ConfigEntry.create_property(self.section(), "number of cores", numCores, self, "NumCores")
        ConfigEntry.create_property(self.section(), "maximum resource size", maxResourceSize, self, "MaxResourceSize")
        ConfigEntry.create_property(self.section(), "maximum memory usage", maxMemorySize, self, "MaxMemorySize")
        ConfigEntry.create_property(self.section(), "use distributed resource management", useDistributedResourceManagement, self, "UseDistributedResourceManagement")
        ConfigEntry.create_property(self.section(), "minimum trust for requesting node", requestingTrust, self, "RequestingTrust")
        ConfigEntry.create_property(self.section(), "minimum trust for computing node", computingTrust, self, "ComputingTrust")
        ConfigEntry.create_property(self.section(), "p2p session timeout", p2pSessionTimeout, self, "P2pSessionTimeout")
        ConfigEntry.create_property(self.section(), "task session timeout", taskSessionTimeout, self, "TaskSessionTimeout")
        ConfigEntry.create_property(self.section(), "resource session timeout", resourceSessionTimeout, self, "ResourceSessionTimeout")
        ConfigEntry.create_property(self.section(), "plugin port", pluginPort, self, "PluginPort")
        ConfigEntry.create_property(self.section(), "eth account name", ethAccount, self, "EthAccount")
        ConfigEntry.create_property(self.section(), "listen of Ip6", useIp6, self, "UseIp6")

    ##############################
    def section(self):
        return self._section

##############################
##############################
class AppConfig:

    CONFIG_LOADED = False

    ##############################
    @classmethod
    def managerPort(cls):
        return MANAGER_PORT

    ##############################
    @classmethod
    def loadConfig(cls, cfgFile = CONFIG_FILENAME):

        logger = logging.getLogger(__name__)

        if cls.CONFIG_LOADED:
            logger.warning("Application already configured")
            return None


        logger.info("Starting generic process service...")
        ps = ProcessService()
        logger.info("Generic process service started")

        logger.info("Trying to register current process")
        localId = ps.register_self()

        if localId < 0:
            logger.error("Failed to register current process - bailing out")
            return None

        cfg  = SimpleConfig(CommonConfig(), NodeConfig(localId), cfgFile)

        cls.CONFIG_LOADED = True

        return AppConfig(cfg)

    ##############################
    def __init__(self, cfg):
        self._cfg = cfg

    ##############################
    def getOptimalPeerNum(self):
        return self._cfg.get_common_config().getOptimalPeerNum()

    def getStartPort(self):
        return self._cfg.get_common_config().getStartPort()

    def getEndPort(self):
        return self._cfg.get_common_config().getEndPort()

    def getManagerAddress(self):
        return self._cfg.get_common_config().getManagerAddress()

    def getManagerListenPort(self):
        return self._cfg.get_common_config().getManagerListenPort()

    def getAppName(self):
        return self._cfg.get_common_config().getAppName()

    def getAppVersion(self):
        return self._cfg.get_common_config().getAppVersion()

    def getDistributedResNum(self):
        return self._cfg.get_common_config().getDistributedResNum()

    def getSeedHost(self):
        return self._cfg.get_node_config().getSeedHost()

    def getSeedHostPort(self):
        return self._cfg.get_node_config().getSeedHostPort()

    def getRootPath(self):
        return self._cfg.get_node_config().getRootPath()

    def getSendPings(self):
        return self._cfg.get_node_config().getSendPings()

    def getPingsInterval(self):
        return self._cfg.get_node_config().getPingsInterval()

    def getClientUid(self):
        return self._cfg.get_node_config().getClientUid()

    def getGettingPeersInterval(self):
        return self._cfg.get_node_config().getGettingPeersInterval()

    def getGettingTasksInterval(self):
        return self._cfg.get_node_config().getGettingTasksInterval()

    def getTaskRequestInterval(self):
        return self._cfg.get_node_config().getTaskRequestInterval()

    def getWaitingForTaskTimeout(self):
        return self._cfg.get_node_config().getWaitingForTaskTimeout()

    def getUseWaitingForTaskTimeout(self):
        return self._cfg.get_node_config().getUseWaitingForTaskTimeout()

    def getEstimatedPerformance(self):
        try:
            return float(self._cfg.get_node_config().getEstimatedPerformance())
        except:
            return float(ESTIMATED_DEFAULT)

    def getNodeSnapshotInterval(self):
        return self._cfg.get_node_config().getNodeSnapshotInterval()

    def getAddTasks(self):
        return self._cfg.get_node_config().getAddTasks()

    def getMaxResultsSendingDelay(self):
        return self._cfg.get_node_config().getMaxResultsSendingDelay()

    def getNumCores (self):
        return self._cfg.get_node_config().getNumCores()

    def getMaxResourceSize (self):
        return self._cfg.get_node_config().getMaxResourceSize()

    def getMaxMemorySize (self):
        return self._cfg.get_node_config().getMaxMemorySize()

    def getUseDistributedResourceManagement(self):
        return self._cfg.get_node_config().getUseDistributedResourceManagement()

    def getRequestingTrust(self):
        return self._cfg.get_node_config().getRequestingTrust()

    def getComputingTrust(self):
        return self._cfg.get_node_config().getComputingTrust()

    def getP2pSessionTimeout(self):
        return self._cfg.get_node_config().getP2pSessionTimeout()

    def getTaskSessionTimeout(self):
        return self._cfg.get_node_config().getTaskSessionTimeout()

    def getResourceSessionTimeout(self):
        return self._cfg.get_node_config().getResourceSessionTimeout()

    def getPluginPort(self):
        return self._cfg.get_node_config().getPluginPort()

    def getEthAccount(self):
        return self._cfg.get_node_config().getEthAccount()

    def getUseIp6(self):
        return self._cfg.get_node_config().getUseIp6()

    ##############################
    def change_config(self, cfgDesc , cfgFile = CONFIG_FILENAME,):
        assert isinstance(cfgDesc, ClientConfigDescriptor)

        self._cfg.get_node_config().setSeedHost(cfgDesc.seedHost)
        self._cfg.get_node_config().setSeedHostPort(cfgDesc.seedHostPort)
        self._cfg.get_node_config().setRootPath(cfgDesc.rootPath)
        self._cfg.get_node_config().setNumCores(cfgDesc.numCores)
        self._cfg.get_node_config().setEstimatedPerformance(cfgDesc.estimatedPerformance)
        self._cfg.get_node_config().setMaxResourceSize(cfgDesc.maxResourceSize)
        self._cfg.get_node_config().setMaxMemorySize(cfgDesc.maxMemorySize)
        self._cfg.get_node_config().setSendPings(cfgDesc.sendPings)
        self._cfg.get_node_config().setPingsInterval(cfgDesc.pingsInterval)
        self._cfg.get_node_config().setGettingPeersInterval(cfgDesc.gettingPeersInterval)
        self._cfg.get_node_config().setGettingTasksInterval(cfgDesc.gettingTasksInterval)
        self._cfg.get_node_config().setTaskRequestInterval(cfgDesc.taskRequestInterval)
        self._cfg.get_node_config().setUseWaitingForTaskTimeout(cfgDesc.useWaitingForTaskTimeout)
        self._cfg.get_node_config().setWaitingForTaskTimeout(cfgDesc.waitingForTaskTimeout)
        self._cfg.get_node_config().setNodeSnapshotInterval(cfgDesc.nodeSnapshotInterval)
        self._cfg.get_node_config().setMaxResultsSendingDelay(cfgDesc.maxResultsSendingDelay)
        self._cfg.get_node_config().setUseDistributedResourceManagement(cfgDesc.useDistributedResourceManagement)
        self._cfg.get_node_config().setRequestingTrust(cfgDesc.requestingTrust)
        self._cfg.get_node_config().setComputingTrust(cfgDesc.computingTrust)
        self._cfg.get_node_config().setP2pSessionTimeout(cfgDesc.p2pSessionTimeout)
        self._cfg.get_node_config().setTaskSessionTimeout(cfgDesc.taskSessionTimeout)
        self._cfg.get_node_config().setResourceSessionTimeout(cfgDesc.resourceSessionTimeout)
        self._cfg.get_node_config().setPluginPort(cfgDesc.pluginPort)
        self._cfg.get_node_config().setEthAccount(cfgDesc.ethAccount)
        self._cfg.get_node_config().setUseIp6(cfgDesc.useIp6)

        self._cfg.get_common_config().setManagerAddress(cfgDesc.managerAddress)
        self._cfg.get_common_config().setManagerListenPort(cfgDesc.managerPort)
        self._cfg.get_common_config().setOptimalPeerNum(cfgDesc.optNumPeers)
        self._cfg.get_common_config().setDistributedResNum(cfgDesc.distResNum)
        SimpleConfig(self._cfg.get_common_config(), self._cfg.get_node_config(), cfgFile, True)

    def __str__(self):
        return str(self._cfg)

if __name__ == "__main__":

    c = AppConfig(0)
    print c
    c = AppConfig(1)
    print c
    c = AppConfig(2)
    print c
