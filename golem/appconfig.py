import logging
from os import path
import sys
from typing import Any, Set

from ethereum.utils import denoms

from golem.config.active import ENABLE_TALKBACK
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.simpleconfig import SimpleConfig, ConfigEntry
from golem.core.variables import KEY_DIFFICULTY

from golem.ranking.helper.trust_const import \
    REQUESTING_TRUST, \
    COMPUTING_TRUST

logger = logging.getLogger(__name__)

MIN_DISK_SPACE = 1024 * 1024
MIN_MEMORY_SIZE = 1024 * 1024
MIN_CPU_CORES = 1
TOTAL_MEMORY_CAP = 0.75

DEFAULT_HARDWARE_PRESET_NAME = "default"
CUSTOM_HARDWARE_PRESET_NAME = "custom"

CONFIG_FILENAME = "app_cfg.ini"

START_PORT = 40102
END_PORT = 60102
RPC_ADDRESS = "localhost"
RPC_PORT = 61000
OPTIMAL_PEER_NUM = 10
SEND_PEERS_NUM = 10

USE_IP6 = 0
USE_UPNP = 1
ACCEPT_TASKS = 1
SEND_PINGS = 1
ENABLE_MONITOR = 1
DEBUG_THIRD_PARTY = 0

PINGS_INTERVALS = 120
GETTING_PEERS_INTERVAL = 4.0
GETTING_TASKS_INTERVAL = 4.0
TASK_REQUEST_INTERVAL = 5.0
PUBLISH_BALANCE_INTERVAL = 3.0
PUBLISH_TASKS_INTERVAL = 1.0
NODE_SNAPSHOT_INTERVAL = 10.0
NETWORK_CHECK_INTERVAL = 10.0
MASK_UPDATE_INTERVAL = 30.0
MAX_SENDING_DELAY = 360
OFFER_POOLING_INTERVAL = 15.0
# How frequently task archive should be saved to disk (in seconds)
TASKARCHIVE_MAINTENANCE_INTERVAL = 30
# Filename for task archive disk file
TASKARCHIVE_FILENAME = "task_archive.pickle"
# Number of past days task archive will store aggregated information for
TASKARCHIVE_NUM_INTERVALS = 365
# Limit of the number  of non-expired tasks stored in task archive at any moment
TASKARCHIVE_MAX_TASKS = 10000000

P2P_SESSION_TIMEOUT = 240
TASK_SESSION_TIMEOUT = 900
RESOURCE_SESSION_TIMEOUT = 600
WAITING_FOR_TASK_SESSION_TIMEOUT = 20
FORWARDED_SESSION_REQUEST_TIMEOUT = 30
COMPUTATION_CANCELLATION_TIMEOUT = 10.0
CLEAN_RESOURES_OLDER_THAN_SECS = 3*24*60*60     # 3 days
CLEAN_TASKS_OLDER_THAN_SECONDS = 3*24*60*60     # 3 days
# FIXME Issue #3862
CLEANING_ENABLED = 0

# Default max price per hour
MAX_PRICE = int(1.0 * denoms.ether)
# Default min price per hour of computation to accept
MIN_PRICE = MAX_PRICE // 10

NET_MASKING_ENABLED = 1
# Expected number of workers =
# max(number of subtasks * INITIAL_MASK_SIZE_FACTOR, MIN_NUM_WORKERS_FOR_MASK)
INITIAL_MASK_SIZE_FACTOR = 1.0
MIN_NUM_WORKERS_FOR_MASK = 20
# Updating by 1 bit increases number of workers 2x
MASK_UPDATE_NUM_BITS = 1

# Experimental temporary banning options
DISALLOW_NODE_TIMEOUT_SECONDS = None
DISALLOW_IP_TIMEOUT_SECONDS = None
DISALLOW_ID_MAX_TIMES = 1
DISALLOW_IP_MAX_TIMES = 1

DEFAULT_HYPERDRIVE_PORT = 3282
DEFAULT_HYPERDRIVE_ADDRESS = None
DEFAULT_HYPERDRIVE_RPC_PORT = 3292
DEFAULT_HYPERDRIVE_RPC_ADDRESS = 'localhost'


class NodeConfig:

    def __init__(self, **kwargs):
        self._section = "Node"

        for k, v in list(kwargs.items()):
            ConfigEntry.create_property(
                self.section(),
                k.replace("_", " "),
                v,
                self,
                k
            )

        self.prop_names = list(kwargs.keys())

    def section(self):
        return self._section


class AppConfig:
    UNSAVED_PROPERTIES = (
        'num_cores',
        'max_resource_size',
        'max_memory_size',
    )

    __loaded_configs = set()  # type: Set[Any]

    @classmethod
    def load_config(cls, datadir, cfg_file_name=CONFIG_FILENAME):

        if ENABLE_TALKBACK and 'pytest' in sys.modules:
            from golem.config import active
            active.ENABLE_TALKBACK = 0

        cfg_file = path.join(datadir, cfg_file_name)
        if cfg_file in cls.__loaded_configs:
            raise RuntimeError("Config has been loaded: {}".format(cfg_file))
        cls.__loaded_configs.add(cfg_file)

        node_config = NodeConfig(
            node_name="",
            node_address="",
            use_ipv6=USE_IP6,
            use_upnp=USE_UPNP,
            start_port=START_PORT,
            end_port=END_PORT,
            rpc_address=RPC_ADDRESS,
            rpc_port=RPC_PORT,
            # peers
            seed_host="",
            seed_port=START_PORT,
            seeds="",
            opt_peer_num=OPTIMAL_PEER_NUM,
            key_difficulty=KEY_DIFFICULTY,
            # flags
            in_shutdown=0,
            accept_tasks=ACCEPT_TASKS,
            send_pings=SEND_PINGS,
            enable_talkback=ENABLE_TALKBACK,
            enable_monitor=ENABLE_MONITOR,
            # hardware
            hardware_preset_name=CUSTOM_HARDWARE_PRESET_NAME,
            # price and trust
            min_price=MIN_PRICE,
            max_price=MAX_PRICE,
            requesting_trust=REQUESTING_TRUST,
            computing_trust=COMPUTING_TRUST,
            # intervals
            pings_interval=PINGS_INTERVALS,
            getting_peers_interval=GETTING_PEERS_INTERVAL,
            getting_tasks_interval=GETTING_TASKS_INTERVAL,
            task_request_interval=TASK_REQUEST_INTERVAL,
            node_snapshot_interval=NODE_SNAPSHOT_INTERVAL,
            network_check_interval=NETWORK_CHECK_INTERVAL,
            mask_update_interval=MASK_UPDATE_INTERVAL,
            max_results_sending_delay=MAX_SENDING_DELAY,
            offer_pooling_interval=OFFER_POOLING_INTERVAL,
            # timeouts
            p2p_session_timeout=P2P_SESSION_TIMEOUT,
            task_session_timeout=TASK_SESSION_TIMEOUT,
            resource_session_timeout=RESOURCE_SESSION_TIMEOUT,
            waiting_for_task_session_timeout=WAITING_FOR_TASK_SESSION_TIMEOUT,
            forwarded_session_request_timeout=FORWARDED_SESSION_REQUEST_TIMEOUT,
            computation_cancellation_timeout=COMPUTATION_CANCELLATION_TIMEOUT,
            clean_resources_older_than_seconds=CLEAN_RESOURES_OLDER_THAN_SECS,
            clean_tasks_older_than_seconds=CLEAN_TASKS_OLDER_THAN_SECONDS,
            cleaning_enabled=CLEANING_ENABLED,
            debug_third_party=DEBUG_THIRD_PARTY,
            # network masking
            net_masking_enabled=NET_MASKING_ENABLED,
            initial_mask_size_factor=INITIAL_MASK_SIZE_FACTOR,
            min_num_workers_for_mask=MIN_NUM_WORKERS_FOR_MASK,
            mask_update_num_bits=MASK_UPDATE_NUM_BITS,
            # acl
            disallow_node_timeout_seconds=DISALLOW_NODE_TIMEOUT_SECONDS,
            disallow_ip_timeout_seconds=DISALLOW_IP_TIMEOUT_SECONDS,
            disallow_id_max_times=DISALLOW_ID_MAX_TIMES,
            disallow_ip_max_times=DISALLOW_IP_MAX_TIMES,
            #hyperg
            hyperdrive_port=DEFAULT_HYPERDRIVE_PORT,
            hyperdrive_address=DEFAULT_HYPERDRIVE_ADDRESS,
            hyperdrive_rpc_port=DEFAULT_HYPERDRIVE_RPC_PORT,
            hyperdrive_rpc_address=DEFAULT_HYPERDRIVE_RPC_ADDRESS,
            # testing
            overwrite_results=None,
        )

        cfg = SimpleConfig(node_config, cfg_file, keep_old=False)
        return cls(cfg, cfg_file)

    def __repr__(self):
        return '<{}: {}>'.format(self.__class__, {
            prop: self.get_node_property(prop)()
            for prop in self._cfg.get_node_config().prop_names
        })

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

        for var, val in list(vars(cfg_desc).items()):
            setter = "set_{}".format(var)
            if not hasattr(self, setter):
                if var in self.UNSAVED_PROPERTIES:
                    logger.debug(
                        "Config property preserved elsewhere: %r", var
                    )
                else:
                    logger.info(
                        "Cannot set unknown config property: %r = %r",
                        var,
                        val,
                    )
                continue

            set_func = getattr(self, setter)
            set_func(val)

        SimpleConfig(self._cfg.get_node_config(),
                     self.config_file, refresh=True)
