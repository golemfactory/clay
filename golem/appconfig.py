from __future__ import absolute_import
import logging
from os import path

from ethereum.utils import denoms
from psutil import virtual_memory

from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.simpleconfig import SimpleConfig, ConfigEntry
from golem.core.simpleenv import SimpleEnv

CONFIG_FILENAME = "app_cfg.ini"
ESTM_FILENAME = "minilight.ini"
MANAGER_PORT = 20301
MANAGER_ADDRESS = "127.0.0.1"
ESTIMATED_DEFAULT = 2220.0
START_PORT = 40102
END_PORT = 60102
RPC_ADDRESS = "localhost"
RPC_PORT = 61000
OPTIMAL_PEER_NUM = 10
MIN_MEMORY_SIZE = 1000 * 1024
MAX_RESOURCE_SIZE = 2 * 1024 * 1024
MAX_MEMORY_SIZE = max(int(virtual_memory().total * 0.75) / 1024, MIN_MEMORY_SIZE)
NUM_CORES = 1
DISTRIBUTED_RES_NUM = 2

logger = logging.getLogger(__name__)


class CommonConfig:

    def __init__(self, section="Common", **kwargs):
        self._section = section

        for k, v in kwargs.iteritems():
            ConfigEntry.create_property(section, k.replace("_", " "), v, self, k)

        self.prop_names = kwargs.keys()

    def section(self):
        return self._section


SEND_PINGS = 1
PINGS_INTERVALS = 120
GETTING_PEERS_INTERVAL = 4.0
GETTING_TASKS_INTERVAL = 4.0
TASK_REQUEST_INTERVAL = 5.0
USE_WAITING_FOR_TASK_TIMEOUT = 0  # defunct
WAITING_FOR_TASK_TIMEOUT = 720  # 36000
WAITING_FOR_TASK_SESSION_TIMEOUT = 20
FORWARDED_SESSION_REQUEST_TIMEOUT = 30
NODE_SNAPSHOT_INTERVAL = 4.0
NETWORK_CHECK_INTERVAL = 1.0
ADD_TASKS = 0
MAX_SENDING_DELAY = 360
USE_DISTRIBUTED_RESOURCE_MANAGEMENT = 1
REQUESTING_TRUST = -1.0
COMPUTING_TRUST = -1.0
P2P_SESSION_TIMEOUT = 240
TASK_SESSION_TIMEOUT = 900
RESOURCE_SESSION_TIMEOUT = 600
PLUGIN_PORT = 1111
ETH_ACCOUNT_NAME = ""
USE_IP6 = 0
ACCEPT_TASKS = 1

# Default max price per hour -- 0.005 ETH ~ 0.05 USD
MAX_PRICE = int(0.005 * denoms.ether)

# Default min price per hour of computation to accept
MIN_PRICE = MAX_PRICE // 10


class NodeConfig:
    @classmethod
    def read_estimated_performance(cls):
        estm_file = SimpleEnv.env_file_name(ESTM_FILENAME)
        res = 0
        try:
            with open(estm_file, 'r') as file_:
                val = file_.read()
                res = "{0:.1f}".format(float(val))
        except IOError as err:
            logger.warning("Can't open file {}: {}".format(estm_file, str(err)))
        except ValueError as err:
            logger.warning("Can't change {} to float: {}".format(val, str(err)))
        return res

    def __init__(self, **kwargs):
        self._section = "Node"

        estimated_performance = NodeConfig.read_estimated_performance()
        if estimated_performance == 0:
            estimated_performance = ESTIMATED_DEFAULT
        kwargs["estimated_performance"] = estimated_performance

        for k, v in kwargs.iteritems():
            ConfigEntry.create_property(self.section(), k.replace("_", " "), v, self, k)

        self.prop_names = kwargs.keys()

    def section(self):
        return self._section


class AppConfig:
    __loaded_configs = set()

    @classmethod
    def manager_port(cls):
        return MANAGER_PORT

    @classmethod
    def load_config(cls, datadir, cfg_file_name=CONFIG_FILENAME):

        # FIXME: This check is only for transition to separeted datadirs.
        cfg_file = path.join(datadir, cfg_file_name)
        assert cfg_file not in cls.__loaded_configs, "Config has been loaded: " + cfg_file
        cls.__loaded_configs.add(cfg_file)

        common_config = CommonConfig(manager_address=MANAGER_ADDRESS,
                                     manager_port=MANAGER_PORT,
                                     start_port=START_PORT,
                                     end_port=END_PORT,
                                     opt_peer_num=OPTIMAL_PEER_NUM,
                                     dist_res_num=DISTRIBUTED_RES_NUM)

        node_config = NodeConfig(node_address="",
                                 rpc_address=RPC_ADDRESS,
                                 rpc_port=RPC_PORT,
                                 seed_host="",
                                 seed_port=START_PORT,
                                 num_cores=NUM_CORES,
                                 max_resource_size=MAX_RESOURCE_SIZE,
                                 max_memory_size=MAX_MEMORY_SIZE,
                                 send_pings=SEND_PINGS,
                                 pings_interval=PINGS_INTERVALS,
                                 getting_peers_interval=GETTING_PEERS_INTERVAL,
                                 getting_tasks_interval=GETTING_TASKS_INTERVAL,
                                 task_request_interval=TASK_REQUEST_INTERVAL,
                                 use_waiting_for_task_timeout=USE_WAITING_FOR_TASK_TIMEOUT,
                                 waiting_for_task_timeout=WAITING_FOR_TASK_TIMEOUT,
                                 waiting_for_task_session_timeout=WAITING_FOR_TASK_SESSION_TIMEOUT,
                                 forwarded_session_request_timeout=FORWARDED_SESSION_REQUEST_TIMEOUT,
                                 node_snapshot_interval=NODE_SNAPSHOT_INTERVAL,
                                 network_check_interval=NETWORK_CHECK_INTERVAL,
                                 add_tasks=ADD_TASKS,
                                 max_results_sending_delay=MAX_SENDING_DELAY,
                                 requesting_trust=REQUESTING_TRUST,
                                 computing_trust=COMPUTING_TRUST,
                                 use_distributed_resource_management=USE_DISTRIBUTED_RESOURCE_MANAGEMENT,
                                 p2p_session_timeout=P2P_SESSION_TIMEOUT,
                                 task_session_timeout=TASK_SESSION_TIMEOUT,
                                 resource_session_timeout=RESOURCE_SESSION_TIMEOUT,
                                 plugin_port=PLUGIN_PORT,
                                 eth_account=ETH_ACCOUNT_NAME,
                                 min_price=MIN_PRICE,
                                 max_price=MAX_PRICE,
                                 use_ipv6=USE_IP6,
                                 accept_tasks=ACCEPT_TASKS,
                                 node_name="",
                                 public_address="",
                                 estimated_lux_performance="0",
                                 estimated_blender_performance="0",
                                 )

        cfg = SimpleConfig(common_config, node_config, cfg_file, keep_old=False)
        return AppConfig(cfg, cfg_file)

    def __init__(self, cfg, config_file):
        self.config_file = config_file
        self._cfg = cfg
        for prop in self._cfg.get_common_config().prop_names:
            setattr(self, "get_{}".format(prop), self.get_common_property(prop))
            setattr(self, "set_{}".format(prop), self.set_common_property(prop))
        for prop in self._cfg.get_node_config().prop_names:
            setattr(self, "get_{}".format(prop), self.get_node_property(prop))
            setattr(self, "set_{}".format(prop), self.set_node_property(prop))

    def get_common_property(self, prop):
        return getattr(self._cfg.get_common_config(), "get_{}".format(prop))

    def set_common_property(self, prop):
        return getattr(self._cfg.get_common_config(), "set_{}".format(prop))

    def get_node_property(self, prop):
        return getattr(self._cfg.get_node_config(), "get_{}".format(prop))

    def set_node_property(self, prop):
        return getattr(self._cfg.get_node_config(), "set_{}".format(prop))

    def change_config(self, cfg_desc):
        assert isinstance(cfg_desc, ClientConfigDescriptor)

        for var, val in vars(cfg_desc).iteritems():
            set_func = getattr(self, "set_{}".format(var))
            set_func(val)
        SimpleConfig(self._cfg.get_common_config(), self._cfg.get_node_config(),
                     self.config_file, refresh=True)
