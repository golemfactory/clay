import logging

logger = logging.getLogger(__name__)


class ClientConfigDescriptor(object):
    """ Keeps information about application configuration. """

    def __init__(self):
        """ Create new basic empty configuration scheme """
        from golem.appconfig import (START_PORT, END_PORT, RPC_ADDRESS, RPC_PORT, OPTIMAL_PEER_NUM, SEND_PINGS,
                                     PINGS_INTERVALS, USE_IP6, GETTING_PEERS_INTERVAL, GETTING_TASKS_INTERVAL,
                                     TASK_REQUEST_INTERVAL, USE_WAITING_FOR_TASK_TIMEOUT, WAITING_FOR_TASK_TIMEOUT,
                                     WAITING_FOR_TASK_SESSION_TIMEOUT, FORWARDED_SESSION_REQUEST_TIMEOUT,
                                     P2P_SESSION_TIMEOUT, TASK_SESSION_TIMEOUT, RESOURCE_SESSION_TIMEOUT,
                                     ESTIMATED_DEFAULT, NODE_SNAPSHOT_INTERVAL, NETWORK_CHECK_INTERVAL,
                                     MAX_SENDING_DELAY, MIN_CPU_CORES, MIN_DISK_SPACE, MIN_MEMORY_SIZE,
                                     DEFAULT_HARDWARE_PRESET_NAME, REQUESTING_TRUST, COMPUTING_TRUST, MIN_PRICE,
                                     MAX_PRICE, ACCEPT_TASKS)
        self.node_name = ""
        self.node_address = ""
        self.start_port = START_PORT
        self.end_port = END_PORT
        self.rpc_address = RPC_ADDRESS
        self.rpc_port = RPC_PORT
        self.opt_peer_num = OPTIMAL_PEER_NUM
        self.send_pings = SEND_PINGS
        self.pings_interval = PINGS_INTERVALS
        self.use_ipv6 = USE_IP6

        self.seed_host = ""
        self.seed_port = 0

        self.getting_peers_interval = GETTING_PEERS_INTERVAL
        self.getting_tasks_interval = GETTING_TASKS_INTERVAL
        self.task_request_interval = TASK_REQUEST_INTERVAL
        self.use_waiting_for_task_timeout = USE_WAITING_FOR_TASK_TIMEOUT
        self.waiting_for_task_timeout = WAITING_FOR_TASK_TIMEOUT
        self.waiting_for_task_session_timeout = WAITING_FOR_TASK_SESSION_TIMEOUT
        self.forwarded_session_request_timeout = FORWARDED_SESSION_REQUEST_TIMEOUT
        self.p2p_session_timeout = P2P_SESSION_TIMEOUT
        self.task_session_timeout = TASK_SESSION_TIMEOUT
        self.resource_session_timeout = RESOURCE_SESSION_TIMEOUT

        self.estimated_performance = ESTIMATED_DEFAULT
        self.estimated_lux_performance = ESTIMATED_DEFAULT
        self.estimated_blender_performance = ESTIMATED_DEFAULT
        self.node_snapshot_interval = NODE_SNAPSHOT_INTERVAL
        self.network_check_interval = NETWORK_CHECK_INTERVAL
        self.max_results_sending_delay = MAX_SENDING_DELAY

        self.num_cores = MIN_CPU_CORES
        self.max_resource_size = MIN_DISK_SPACE
        self.max_memory_size = MIN_MEMORY_SIZE
        self.hardware_preset_name = DEFAULT_HARDWARE_PRESET_NAME

        self.use_distributed_resource_management = 1

        self.requesting_trust = REQUESTING_TRUST
        self.computing_trust = COMPUTING_TRUST

        self.eth_account = ""
        self.min_price = MIN_PRICE
        self.max_price = MAX_PRICE
        self.public_address = ""

        self.accept_tasks = ACCEPT_TASKS

    def init_from_app_config(self, app_config):
        """Initializes config parameters based on the specified AppConfig
        :param app_config: instance of AppConfig
        :return:
        """
        for name in vars(self):
            getter = 'get_' + name
            if not hasattr(app_config, getter):
                logger.info("Cannot read unknown config parameter: {}"
                            .format(name))
                continue
            setattr(self, name, getattr(app_config, getter)())


class ConfigApprover(object):
    """Change specific config description option from strings to the right
       format. Doesn't change them if they're in a wrong format (they're
       saved as strings then).
       """

    dont_change_opt = ['seed_host', 'max_resource_size', 'max_memory_size',
                       'use_distributed_resource_management', 'use_waiting_for_task_timeout', 'send_pings',
                       'use_ipv6', 'eth_account', 'accept_tasks', 'node_name']
    to_int_opt = ['seed_port', 'num_cores', 'opt_peer_num', 'waiting_for_task_timeout', 'p2p_session_timeout',
                  'task_session_timeout', 'pings_interval', 'max_results_sending_delay',
                  'min_price', 'max_price']
    to_float_opt = ['estimated_performance', 'estimated_lux_performance', 'estimated_blender_performance',
                    'getting_peers_interval', 'getting_tasks_interval', 'computing_trust', 'requesting_trust']

    numeric_opt = to_int_opt + to_float_opt

    def __init__(self, config_desc):
        """ Create config approver class that keeps old config descriptor
        :param ClientConfigDescriptor config_desc: old config descriptor that
                                                   may be modified in the
                                                   future
        """
        self.config_desc = config_desc
        self._actions = {}
        self._opts_to_change = self.dont_change_opt + self.numeric_opt
        self._init_actions()

    def change_config(self, new_config_desc):
        """Try to change specific configuration options in the old config
           for a values from new config. Try to change new config options to
           the right format (int or float) if it's expected.
        :param ClientConfigDescriptor new_config_desc: new config descriptor
        :return ClientConfigDescriptor: changed config descriptor
        """
        ncd_dict = new_config_desc.__dict__
        change_dict = {
            k: ncd_dict[k]
            for k in self._opts_to_change if k in self._opts_to_change
        }
        for key, val in list(change_dict.items()):
            change_dict[key] = self._actions[key](val, key)
        self.config_desc.__dict__.update(change_dict)
        return self.config_desc

    def _init_actions(self):
        for opt in self.dont_change_opt:
            self._actions[opt] = ConfigApprover._empty_action
        for opt in self.to_int_opt:
            self._actions[opt] = ConfigApprover._to_int
        for opt in self.to_float_opt:
            self._actions[opt] = ConfigApprover._to_float

    @staticmethod
    def _empty_action(val, name):
        """ Return value val without making any changes """
        return val

    @staticmethod
    def _to_int(val, name):
        """ Try to change value <val> to int. If it's not possible return unchanged val
        :param val: value that should be changed to int
        :param str name: name of a config description option for logs
        :return: value change to int or unchanged value if it's not possible
        """
        try:
            return int(val)
        except ValueError:
            logger.warning("{} value '{}' is not a number".format(name, val))
        return val

    @staticmethod
    def _to_float(val, name):
        """Try to change value <val> to float. If it's not possible
           return unchanged val
        :param val: value that should be changed to float
        :param str name: name of a config description option for logs
        :return: value change to float or unchanged value if it's not possible
        """
        try:
            return float(val)
        except ValueError:
            logger.warning("{} value '{}' is not a number".format(name, val))
        return val
