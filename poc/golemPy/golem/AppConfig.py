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
                  manager_address = MANAGER_ADDRESS,
                  manager_port = MANAGER_PORT,
                  start_port = START_PORT,
                  end_port = END_PORT,
                  optimalPeerNum = OPTIMAL_PEER_NUM,
                  distributedResNum = DISTRIBUTED_RES_NUM,
                  app_name = APP_NAME,
                  app_version = APP_VERSION):

        self._section = section

        ConfigEntry.create_property(section, "optimal peer num",    optimalPeerNum,    self, "OptimalPeerNum")
        ConfigEntry.create_property(section, "start port",          start_port, self, "StartPort")
        ConfigEntry.create_property(section, "end port",            end_port, self, "EndPort")
        ConfigEntry.create_property(section, "manager address", manager_address, self, "ManagerAddress")
        ConfigEntry.create_property(section, "manager listen port", manager_port, self, "ManagerListenPort")
        ConfigEntry.create_property(section, "distributed res num", distributedResNum, self, "DistributedResNum")
        ConfigEntry.create_property(section, "application name", app_name, self, "AppName")
        ConfigEntry.create_property(section, "application version", app_version, self, "AppVersion")

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
    def __init__(self, node_id, seed_host = "", seedPort = 0, root_path = DEFAULT_ROOT_PATH, num_cores = 4,
                  max_resource_size = MAX_RESOURCE_SIZE, max_memory_size = MAX_MEMORY_SIZE,
                  send_pings = SEND_PINGS, pings_interval = PINGS_INTERVALS,
                  getting_peers_interval = GETTING_PEERS_INTERVAL, getting_tasks_interval = GETTING_TASKS_INTERVAL,
                  task_request_interval = TASK_REQUEST_INTERVAL, use_waiting_for_task_timeout = USE_WAITING_FOR_TASK_TIMEOUT,
                  waiting_for_task_timeout = WAITING_FOR_TASK_TIMEOUT, nodesSnapshotInterval = NODE_SNAPSHOT_INTERVAL,
                  add_tasks = ADD_TASKS, maxSendingDelay = MAX_SENDING_DELAY,
                  requesting_trust = REQUESTING_TRUST, computing_trust = COMPUTING_TRUST,
                  use_distributed_resource_management = USE_DISTRIBUTED_RESOURCE_MANAGEMENT,
                  p2p_session_timeout = P2P_SESSION_TIMEOUT, task_session_timeout = TASK_SESSION_TIMEOUT,
                  resource_session_timeout = RESOURCE_SESSION_TIMEOUT, plugin_port = PLUGIN_PORT,
                  eth_account = ETH_ACCOUNT_NAME, use_ipv6 = USE_IP6):
        self._section = "Node {}".format(node_id)

        estimated = NodeConfig.readEstimatedPerformance()
        if estimated == 0:
            estimated = ESTIMATED_DEFAULT

        ConfigEntry.create_property(self.section(), "seed host", seed_host, self, "SeedHost")
        ConfigEntry.create_property(self.section(), "seed host port", seedPort, self, "SeedHostPort")
        ConfigEntry.create_property(self.section(), "resource root path", root_path, self, "RootPath")
        ConfigEntry.create_property(self.section(), "send pings", send_pings, self, "SendPings")
        ConfigEntry.create_property(self.section(), "pings interval", pings_interval, self, "PingsInterval")
        ConfigEntry.create_property(self.section(), "client UUID", u"",   self, "ClientUid")
        ConfigEntry.create_property(self.section(), "getting peers interval",getting_peers_interval, self, "GettingPeersInterval")
        ConfigEntry.create_property(self.section(), "getting tasks interval", getting_tasks_interval, self, "GettingTasksInterval")
        ConfigEntry.create_property(self.section(), "task request interval", task_request_interval, self, "TaskRequestInterval")
        ConfigEntry.create_property(self.section(), "use waiting for task timeout", use_waiting_for_task_timeout, self, "UseWaitingForTaskTimeout")
        ConfigEntry.create_property(self.section(), "waiting for task timeout", waiting_for_task_timeout, self, "WaitingForTaskTimeout")
        ConfigEntry.create_property(self.section(), "estimated perfomance", estimated,  self, "EstimatedPerformance")
        ConfigEntry.create_property(self.section(), "node snapshot interval", nodesSnapshotInterval,  self, "NodeSnapshotInterval")
        ConfigEntry.create_property(self.section(), "add tasks", add_tasks, self, "AddTasks")
        ConfigEntry.create_property(self.section(), "maximum delay for sending task results", maxSendingDelay,  self, "MaxResultsSendingDelay")
        ConfigEntry.create_property(self.section(), "number of cores", num_cores, self, "NumCores")
        ConfigEntry.create_property(self.section(), "maximum resource size", max_resource_size, self, "MaxResourceSize")
        ConfigEntry.create_property(self.section(), "maximum memory usage", max_memory_size, self, "MaxMemorySize")
        ConfigEntry.create_property(self.section(), "use distributed resource management", use_distributed_resource_management, self, "UseDistributedResourceManagement")
        ConfigEntry.create_property(self.section(), "minimum trust for requesting node", requesting_trust, self, "RequestingTrust")
        ConfigEntry.create_property(self.section(), "minimum trust for computing node", computing_trust, self, "ComputingTrust")
        ConfigEntry.create_property(self.section(), "p2p session timeout", p2p_session_timeout, self, "P2pSessionTimeout")
        ConfigEntry.create_property(self.section(), "task session timeout", task_session_timeout, self, "TaskSessionTimeout")
        ConfigEntry.create_property(self.section(), "resource session timeout", resource_session_timeout, self, "ResourceSessionTimeout")
        ConfigEntry.create_property(self.section(), "plugin port", plugin_port, self, "PluginPort")
        ConfigEntry.create_property(self.section(), "eth account name", eth_account, self, "EthAccount")
        ConfigEntry.create_property(self.section(), "listen of Ip6", use_ipv6, self, "UseIp6")

    ##############################
    def section(self):
        return self._section

##############################
##############################
class AppConfig:

    CONFIG_LOADED = False

    ##############################
    @classmethod
    def manager_port(cls):
        return MANAGER_PORT

    ##############################
    @classmethod
    def load_config(cls, cfgFile = CONFIG_FILENAME):

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
    def get_optimal_peer_num(self):
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

    def get_root_path(self):
        return self._cfg.get_node_config().getRootPath()

    def get_send_pings(self):
        return self._cfg.get_node_config().get_send_pings()

    def getPingsInterval(self):
        return self._cfg.get_node_config().getPingsInterval()

    def getClientUid(self):
        return self._cfg.get_node_config().getClientUid()

    def getGettingPeersInterval(self):
        return self._cfg.get_node_config().getGettingPeersInterval()

    def getGettingTasksInterval(self):
        return self._cfg.get_node_config().getGettingTasksInterval()

    def get_taskRequestInterval(self):
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

    def get_requesting_trust(self):
        return self._cfg.get_node_config().getRequestingTrust()

    def getComputingTrust(self):
        return self._cfg.get_node_config().getComputingTrust()

    def getP2pSessionTimeout(self):
        return self._cfg.get_node_config().getP2pSessionTimeout()

    def get_taskSessionTimeout(self):
        return self._cfg.get_node_config().getTaskSessionTimeout()

    def getResourceSessionTimeout(self):
        return self._cfg.get_node_config().getResourceSessionTimeout()

    def get_plugin_port(self):
        return self._cfg.get_node_config().getPluginPort()

    def get_eth_account(self):
        return self._cfg.get_node_config().getEthAccount()

    def getUseIp6(self):
        return self._cfg.get_node_config().getUseIp6()

    ##############################
    def change_config(self, cfgDesc , cfgFile = CONFIG_FILENAME,):
        assert isinstance(cfgDesc, ClientConfigDescriptor)

        self._cfg.get_node_config().setSeedHost(cfgDesc.seed_host)
        self._cfg.get_node_config().setSeedHostPort(cfgDesc.seed_host_port)
        self._cfg.get_node_config().setRootPath(cfgDesc.root_path)
        self._cfg.get_node_config().setNumCores(cfgDesc.num_cores)
        self._cfg.get_node_config().setEstimatedPerformance(cfgDesc.estimated_performance)
        self._cfg.get_node_config().setMaxResourceSize(cfgDesc.max_resource_size)
        self._cfg.get_node_config().setMaxMemorySize(cfgDesc.max_memory_size)
        self._cfg.get_node_config().setSendPings(cfgDesc.send_pings)
        self._cfg.get_node_config().setPingsInterval(cfgDesc.pings_interval)
        self._cfg.get_node_config().setGettingPeersInterval(cfgDesc.getting_peers_interval)
        self._cfg.get_node_config().setGettingTasksInterval(cfgDesc.getting_tasks_interval)
        self._cfg.get_node_config().setTaskRequestInterval(cfgDesc.task_request_interval)
        self._cfg.get_node_config().setUseWaitingForTaskTimeout(cfgDesc.use_waiting_for_task_timeout)
        self._cfg.get_node_config().setWaitingForTaskTimeout(cfgDesc.waiting_for_task_timeout)
        self._cfg.get_node_config().setNodeSnapshotInterval(cfgDesc.node_snapshot_interval)
        self._cfg.get_node_config().setMaxResultsSendingDelay(cfgDesc.max_results_sending_delay)
        self._cfg.get_node_config().setUseDistributedResourceManagement(cfgDesc.use_distributed_resource_management)
        self._cfg.get_node_config().setRequestingTrust(cfgDesc.requesting_trust)
        self._cfg.get_node_config().setComputingTrust(cfgDesc.computing_trust)
        self._cfg.get_node_config().setP2pSessionTimeout(cfgDesc.p2p_session_timeout)
        self._cfg.get_node_config().setTaskSessionTimeout(cfgDesc.task_session_timeout)
        self._cfg.get_node_config().setResourceSessionTimeout(cfgDesc.resource_session_timeout)
        self._cfg.get_node_config().setPluginPort(cfgDesc.plugin_port)
        self._cfg.get_node_config().setEthAccount(cfgDesc.eth_account)
        self._cfg.get_node_config().setUseIp6(cfgDesc.use_ipv6)

        self._cfg.get_common_config().setManagerAddress(cfgDesc.manager_address)
        self._cfg.get_common_config().setManagerListenPort(cfgDesc.manager_port)
        self._cfg.get_common_config().setOptimalPeerNum(cfgDesc.opt_num_peers)
        self._cfg.get_common_config().setDistributedResNum(cfgDesc.dist_res_num)
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
