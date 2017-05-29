from __future__ import absolute_import

import logging
from os import path

from ethereum.utils import denoms

from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.simpleconfig import SimpleConfig, ConfigEntry
from golem.core.simpleenv import SimpleEnv

logger = logging.getLogger(__name__)

MIN_DISK_SPACE = 1000 * 1024
MIN_MEMORY_SIZE = 1000 * 1024
MIN_CPU_CORES = 1

DEFAULT_HARDWARE_PRESET_NAME = u"default"
CUSTOM_HARDWARE_PRESET_NAME = u"custom"

CONFIG_FILENAME = "app_cfg.ini"
ESTM_FILENAME = "minilight.ini"

START_PORT = 40102
END_PORT = 60102
RPC_ADDRESS = "localhost"
RPC_PORT = 61000
OPTIMAL_PEER_NUM = 10

ESTIMATED_DEFAULT = 2220.0

USE_IP6 = 0
ACCEPT_TASKS = 1
SEND_PINGS = 1

PINGS_INTERVALS = 120
GETTING_PEERS_INTERVAL = 4.0
GETTING_TASKS_INTERVAL = 4.0
TASK_REQUEST_INTERVAL = 5.0
PUBLISH_BALANCE_INTERVAL = 3.0
PUBLISH_TASKS_INTERVAL = 1.0
NODE_SNAPSHOT_INTERVAL = 10.0
NETWORK_CHECK_INTERVAL = 10.0
MAX_SENDING_DELAY = 360

P2P_SESSION_TIMEOUT = 240
TASK_SESSION_TIMEOUT = 900
RESOURCE_SESSION_TIMEOUT = 600
USE_WAITING_FOR_TASK_TIMEOUT = 0  # defunct
WAITING_FOR_TASK_TIMEOUT = 720  # 36000
WAITING_FOR_TASK_SESSION_TIMEOUT = 20
FORWARDED_SESSION_REQUEST_TIMEOUT = 30

# Default max price per hour -- 5.0 GNT ~ 0.05 USD
MAX_PRICE = int(5.0 * denoms.ether)
# Default min price per hour of computation to accept
MIN_PRICE = MAX_PRICE // 10

REQUESTING_TRUST = -1.0
COMPUTING_TRUST = -1.0


# FIXME: deprecated
class CommonConfig:

    def __init__(self, section="Common", **kwargs):
        self._section = section

        for k, v in kwargs.iteritems():
            ConfigEntry.create_property(
                section,
                k.replace("_", " "),
                v,
                self,
                k
            )

        self.prop_names = kwargs.keys()

    def section(self):
        return self._section


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
            ConfigEntry.create_property(
                self.section(),
                k.replace("_", " "),
                v,
                self,
                k
            )

        self.prop_names = kwargs.keys()

    def section(self):
        return self._section


class AppConfig:
    __loaded_configs = set()

    @classmethod
    def load_config(cls, datadir, cfg_file_name=CONFIG_FILENAME):

        # FIXME: This check is only for transition to separated datadirs.
        cfg_file = path.join(datadir, cfg_file_name)
        if cfg_file in cls.__loaded_configs:
            raise RuntimeError("Config has been loaded: {}".format(cfg_file))
        cls.__loaded_configs.add(cfg_file)

        node_config = NodeConfig(
            node_name="",
            node_address="",
            public_address="",
            eth_account="",
            use_ipv6=USE_IP6,
            start_port=START_PORT,
            end_port=END_PORT,
            rpc_address=RPC_ADDRESS,
            rpc_port=RPC_PORT,
            # peers
            seed_host="",
            seed_port=START_PORT,
            opt_peer_num=OPTIMAL_PEER_NUM,
            # flags
            accept_tasks=ACCEPT_TASKS,
            send_pings=SEND_PINGS,
            # hardware
            hardware_preset_name=CUSTOM_HARDWARE_PRESET_NAME,
            # price and trust
            min_price=MIN_PRICE,
            max_price=MAX_PRICE,
            requesting_trust=REQUESTING_TRUST,
            computing_trust=COMPUTING_TRUST,
            # benchmarks
            estimated_lux_performance="0",
            estimated_blender_performance="0",
            # intervals
            pings_interval=PINGS_INTERVALS,
            getting_peers_interval=GETTING_PEERS_INTERVAL,
            getting_tasks_interval=GETTING_TASKS_INTERVAL,
            task_request_interval=TASK_REQUEST_INTERVAL,
            node_snapshot_interval=NODE_SNAPSHOT_INTERVAL,
            network_check_interval=NETWORK_CHECK_INTERVAL,
            max_results_sending_delay=MAX_SENDING_DELAY,
            # timeouts
            p2p_session_timeout=P2P_SESSION_TIMEOUT,
            task_session_timeout=TASK_SESSION_TIMEOUT,
            resource_session_timeout=RESOURCE_SESSION_TIMEOUT,
            use_waiting_for_task_timeout=USE_WAITING_FOR_TASK_TIMEOUT,
            waiting_for_task_timeout=WAITING_FOR_TASK_TIMEOUT,
            waiting_for_task_session_timeout=WAITING_FOR_TASK_SESSION_TIMEOUT,
            forwarded_session_request_timeout=FORWARDED_SESSION_REQUEST_TIMEOUT)

        cfg = SimpleConfig(node_config, cfg_file, keep_old=False)
        return AppConfig(cfg, cfg_file)

    def __init__(self, cfg, config_file):
        self.config_file = config_file
        self._cfg = cfg
        for prop in self._cfg.get_node_config().prop_names:
            setattr(self, "get_{}".format(prop), self.get_node_property(prop))
            setattr(self, "set_{}".format(prop), self.set_node_property(prop))

    def get_node_property(self, prop):
        return getattr(self._cfg.get_node_config(), "get_{}".format(prop))

    def set_node_property(self, prop):
        return getattr(self._cfg.get_node_config(), "set_{}".format(prop))

    def change_config(self, cfg_desc):
        if not isinstance(cfg_desc, ClientConfigDescriptor):
            raise TypeError(
                "Incorrect config descriptor type: {}."
                " Should be ClientConfigDescriptor"
                .format(type(cfg_desc))
            )

        for var, val in vars(cfg_desc).iteritems():
            setter = "set_{}".format(var)
            if not hasattr(self, setter):
                logger.info("Cannot set unknown config property: {} = {}"
                            .format(var, val))
                continue

            set_func = getattr(self, setter)
            set_func(val)

        SimpleConfig(self._cfg.get_node_config(),
                     self.config_file, refresh=True)
