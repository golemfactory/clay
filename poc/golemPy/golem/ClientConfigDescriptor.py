import logging

logger = logging.getLogger(__name__)


class ClientConfigDescriptor(object):
    """ Keeps information about application configuration. """

    def __init__(self):
        """ Create new basic empty configuration scheme """
        self.client_uid = 0
        self.start_port = 0
        self.end_port = 0
        self.manager_address = ""
        self.manager_port = 0
        self.opt_num_peers = 0
        self.send_pings = 0
        self.pings_interval = 0.0
        self.add_tasks = 0
        self.dist_res_num = 0
        self.client_version = 0
        self.use_ipv6 = 0

        self.seed_host = u""
        self.seed_host_port = 0

        self.plugin_port = 0

        self.getting_peers_interval = 0.0
        self.getting_tasks_interval = 0.0
        self.task_request_interval = 0.0
        self.use_waiting_for_task_timeout = 0
        self.waiting_for_task_timeout = 0.0
        self.p2p_session_timeout = 0
        self.task_session_timeout = 0
        self.resource_session_timeout = 0

        self.estimated_performance = 0.0
        self.node_snapshot_interval = 0.0
        self.max_results_sending_delay = 0.0
        self.root_path = u""
        self.num_cores = 0
        self.max_resource_size = 0
        self.max_memory_size = 0

        self.use_distributed_resource_management = True

        self.requesting_trust = 0.0
        self.computing_trust = 0.0

        self.app_name = ""
        self.app_version = ""
        self.eth_account = ""


class ConfigApprover(object):
    """ Change specific config description option from strings to the right format. Doesn't change
     them if they're in a wrong format (they're saved as strings then). """

    def __init__(self, config_desc):
        """ Create config approver class that keeps old config descriptor
        :param ClientConfigDescriptor config_desc: old config descriptor that may be modified in the future
        """
        self.config_desc = config_desc
        self._actions = {}
        self._opts_to_change = []
        self._init_actions()

    def change_config(self, new_config_desc):
        """ Try to change specific configuration options in the old config for a values from new config. Try to
        change new config options to the right format (int or float) if it's expected.
        :param ClientConfigDescriptor new_config_desc: new config descriptor
        :return ClientConfigDescriptor: changed config descriptor
        """
        ncd_dict = new_config_desc.__dict__
        change_dict = {k: ncd_dict[k] for k in self._opts_to_change if k in self._opts_to_change}
        for key, val in change_dict.iteritems():
            change_dict[key] = self._actions[key](val, key)
        self.config_desc.__dict__.update(change_dict)
        return self.config_desc

    def _init_actions(self):
        dont_change_opt = ['seed_host', 'root_path', 'max_resource_size', 'max_memory_size',
                           'use_distributed_resource_management', 'use_waiting_for_task_timeout', 'send_pings',
                           'use_ipv6', 'eth_account', 'root_path']
        to_int_opt = ['seed_host_port', 'manager_port', 'num_cores', 'opt_num_peers', 'dist_res_num',
                      'waiting_for_task_timeout', 'p2p_session_timeout', 'task_session_timeout',
                      'resource_session_timeout', 'pings_interval', 'max_results_sending_delay', ]
        to_float_opt = ['estimated_performance', 'getting_peers_interval', 'getting_tasks_interval',
                        'node_snapshot_interval', 'computing_trust', 'requesting_trust']
        self._opts_to_change = dont_change_opt + to_int_opt + to_float_opt
        for opt in dont_change_opt:
            self._actions[opt] = ConfigApprover._empty_action
        for opt in to_int_opt:
            self._actions[opt] = ConfigApprover._to_int
        for opt in to_float_opt:
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
            new_val = int(val)
        except ValueError:
            logger.warning("{} value '{}' is not a number".format(name, val))
            return val
        return new_val

    @staticmethod
    def _to_float(val, name):
        """ Try to change value <val> to float. If it's not possible return unchanged val
        :param val: value that should be changed to float
        :param str name: name of a config description option for logs
        :return: value change to float or unchanged value if it's not possible
        """
        try:
            new_val = float(val)
        except ValueError:
            logger.warning("{} value '{}' is not a number".format(name, val))
            return val
        return new_val
