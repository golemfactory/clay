import logging
import appdirs
from os import path

from golem.core.simpleconfig import SimpleConfig, ConfigEntry
from golem.core.simpleenv import SimpleEnv
from golem.core.prochelper import ProcessService
from golem.clientconfigdescriptor import ClientConfigDescriptor

CONFIG_FILENAME = "app_cfg.ini"
ESTM_FILENAME = "minilight.ini"
ESTM_LUX_FILENAME = "lux.ini"
ESTM_BLENDER_FILENAME = "blender.ini"
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
USE_WAITING_FOR_TASK_TIMEOUT = 0
WAITING_FOR_TASK_TIMEOUT = 36000
NODE_SNAPSHOT_INTERVAL = 4.0
ADD_TASKS = 0
MAX_SENDING_DELAY = 360
USE_DISTRIBUTED_RESOURCE_MANAGEMENT = 1
DEFAULT_ROOT_PATH = appdirs.user_data_dir('golem')
REQUESTING_TRUST = -1.0
COMPUTING_TRUST = -1.0
P2P_SESSION_TIMEOUT = 240
TASK_SESSION_TIMEOUT = 900
RESOURCE_SESSION_TIMEOUT = 600
PLUGIN_PORT = 1111
ETH_ACCOUNT_NAME = ""
USE_IP6 = 0


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

    @classmethod
    def read_estimated_lux_performance(cls):
        estm_file = SimpleEnv.env_file_name(ESTM_LUX_FILENAME)
        res = 0
        if path.isfile(estm_file):
            try:
                with open(estm_file, 'r') as file_:
                    res = "{0:.1f}".format(float(file_.read()))
            except:
                return 0
        return res

    @classmethod
    def read_estimated_blender_performance(cls):
        estm_file = SimpleEnv.env_file_name(ESTM_BLENDER_FILENAME)
        res = 0
        if path.isfile(estm_file):
            try:
                with open(estm_file, 'r') as file_:
                    res = "{0:.1f}".format(float(file_.read()))
            except:
                return 0
        return res

    def __init__(self, node_id, **kwargs):
        self._section = "Node {}".format(node_id)

        estimated_performance = NodeConfig.read_estimated_performance()
        if estimated_performance == 0:
            estimated_performance = ESTIMATED_DEFAULT
        kwargs["estimated_performance"] = estimated_performance

        estimated_lux = NodeConfig.read_estimated_lux_performance()
        if estimated_lux <= 0:
            estimated_lux = ESTIMATED_DEFAULT
        kwargs["estimated_lux_performance"] = estimated_lux

        estimated_blender = NodeConfig.read_estimated_blender_performance()
        if estimated_blender <= 0:
            estimated_blender = ESTIMATED_DEFAULT
        kwargs["estimated_blender_performance"] = estimated_blender

        for k, v in kwargs.iteritems():
            ConfigEntry.create_property(self.section(), k.replace("_", " "), v, self, k)

        self.prop_names = kwargs.keys()

    def section(self):
        return self._section


class AppConfig:
    CONFIG_LOADED = False

    @classmethod
    def manager_port(cls):
        return MANAGER_PORT

    @classmethod
    def load_config(cls, cfg_file=CONFIG_FILENAME):

        if cls.CONFIG_LOADED:
            logger.warning("Application already configured")
            return None

        logger.info("Starting generic process service...")
        ps = ProcessService()
        logger.info("Generic process service started")

        logger.info("Trying to register current process")
        local_id = ps.register_self()

        if local_id < 0:
            logger.error("Failed to register current process - bailing out")
            return None

        common_config = CommonConfig(manager_address=MANAGER_ADDRESS,
                                     manager_port=MANAGER_PORT,
                                     start_port=START_PORT,
                                     end_port=END_PORT,
                                     opt_peer_num=OPTIMAL_PEER_NUM,
                                     dist_res_num=DISTRIBUTED_RES_NUM,
                                     app_name=APP_NAME,
                                     app_version=APP_VERSION)

        node_config = NodeConfig(local_id,
                                 node_address="",
                                 seed_host="",
                                 seed_port=0,
                                 root_path=DEFAULT_ROOT_PATH,
                                 num_cores=4,
                                 max_resource_size=MAX_RESOURCE_SIZE,
                                 max_memory_size=MAX_MEMORY_SIZE,
                                 send_pings=SEND_PINGS,
                                 pings_interval=PINGS_INTERVALS,
                                 getting_peers_interval=GETTING_PEERS_INTERVAL,
                                 getting_tasks_interval=GETTING_TASKS_INTERVAL,
                                 task_request_interval=TASK_REQUEST_INTERVAL,
                                 use_waiting_for_task_timeout=USE_WAITING_FOR_TASK_TIMEOUT,
                                 waiting_for_task_timeout=WAITING_FOR_TASK_TIMEOUT,
                                 node_snapshot_interval=NODE_SNAPSHOT_INTERVAL,
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
                                 use_ipv6=USE_IP6,
                                 node_name="",
                                 public_address="")

        cfg = SimpleConfig(common_config, node_config, cfg_file)

        cls.CONFIG_LOADED = True

        return AppConfig(cfg)

    def __init__(self, cfg):
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

    def change_config(self, cfg_desc, cfg_file=CONFIG_FILENAME, ):
        assert isinstance(cfg_desc, ClientConfigDescriptor)

        for var, val in vars(cfg_desc).iteritems():
            set_func = getattr(self, "set_{}".format(var))
            set_func(val)
        SimpleConfig(self._cfg.get_common_config(), self._cfg.get_node_config(), cfg_file, refresh=True,
                     check_uid=False)

    def __str__(self):
        return str(self._cfg)
