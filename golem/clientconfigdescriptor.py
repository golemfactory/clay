import logging
import typing

from golem.core.variables import KEY_DIFFICULTY

logger = logging.getLogger(__name__)


class ClientConfigDescriptor(object):
    """ Keeps information about application configuration. """

    def __init__(self):
        """ Create new basic empty configuration scheme """
        self.node_name: typing.Optional[str] = None
        self.node_address: typing.Optional[str] = None
        self.start_port: typing.Optional[int] = None
        self.end_port: typing.Optional[int] = None
        self.rpc_address: typing.Optional[str] = None
        self.rpc_port: typing.Optional[int] = None
        self.opt_peer_num = 0
        self.send_pings = 0
        self.pings_interval = 0.0
        self.use_ipv6 = 0
        self.key_difficulty = 0
        self.use_upnp = 0
        self.enable_talkback = 0
        self.enable_monitor = 0

        self.seed_host = None
        self.seed_port = 0
        self.seeds = ""

        self.getting_peers_interval = 0.0
        self.getting_tasks_interval = 0.0
        self.task_request_interval = 0.0
        self.waiting_for_task_session_timeout = 0.0
        self.forwarded_session_request_timeout = 0.0
        self.computation_cancellation_timeout = 0.0
        self.p2p_session_timeout = 0
        self.task_session_timeout = 0
        self.resource_session_timeout = 0
        self.clean_resources_older_than_seconds = 0
        self.clean_tasks_older_than_seconds = 0
        self.cleaning_enabled = 0
        self.offer_pooling_interval = 0.0

        self.node_snapshot_interval = 0.0
        self.network_check_interval = 0.0
        self.max_results_sending_delay = 0.0

        self.num_cores = 0
        self.max_resource_size = 0  # KiB
        self.max_memory_size = 0  # KiB
        self.hardware_preset_name = ""

        self.requesting_trust = 0.0
        self.computing_trust = 0.0

        self.min_price = 0
        self.max_price = 0

        self.accept_tasks = 1
        self.debug_third_party = 0
        self.in_shutdown = 0

        self.net_masking_enabled = 0
        self.initial_mask_size_factor = 0
        self.min_num_workers_for_mask = 0
        self.mask_update_interval = 0
        self.mask_update_num_bits = 0

        self.disallow_node_timeout_seconds: typing.Optional[int] = None
        self.disallow_ip_timeout_seconds: typing.Optional[int] = None

        self.disallow_id_max_times = 1
        self.disallow_ip_max_times = 1

        self.hyperdrive_port: typing.Optional[int] = None
        self.hyperdrive_address: typing.Optional[str] = None
        self.hyperdrive_rpc_port: typing.Optional[int] = None
        self.hyperdrive_rpc_address: typing.Optional[str] = None

        self.overwrite_results: typing.Optional[str] = None

    def __repr__(self):
        return '{}: {}'.format(self.__class__, {
            v: getattr(self, v) for v in vars(self)})

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
    to_int_opt = {
        'seed_port', 'num_cores', 'opt_peer_num', 'p2p_session_timeout',
        'task_session_timeout', 'pings_interval', 'max_results_sending_delay',
        'key_difficulty',
    }
    to_big_int_opt = {
        'min_price', 'max_price',
    }
    to_float_opt = {
        'getting_peers_interval', 'getting_tasks_interval', 'computing_trust',
        'requesting_trust'
    }
    max_opt = {'key_difficulty': KEY_DIFFICULTY}

    def __init__(self, config_desc):
        """ Create config approver class that keeps old config descriptor
        :param ClientConfigDescriptor config_desc: old config descriptor that
                                                   may be modified in the
                                                   future
        """
        self._actions = [
            (self.to_int_opt, self._to_int),
            (self.to_big_int_opt, self._to_int),
            (self.to_float_opt, self._to_float),
            (self.max_opt, self._max_value)
        ]
        self.config_desc = config_desc

    def approve(self):
        return self.change_config(self.config_desc)

    def change_config(self, new_config_desc):
        """Try to change specific configuration options in the old config
           for a values from new config. Try to change new config options to
           the right format (int or float) if it's expected.
        :param ClientConfigDescriptor new_config_desc: new config descriptor
        :return ClientConfigDescriptor: changed config descriptor
        """
        for key, val in new_config_desc.__dict__.items():
            for keys, action in self._actions:
                if key in keys:
                    val = action(val, key)
                    setattr(self.config_desc, key, val)
        return self.config_desc

    @classmethod
    def is_numeric(cls, name: str) -> bool:
        return (
            name in cls.to_int_opt or
            name in cls.to_float_opt or
            name in cls.to_big_int_opt
        )

    @classmethod
    def is_big_int(cls, name: str) -> bool:
        return name in cls.to_big_int_opt

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

    @classmethod
    def _max_value(cls, val, name):
        """Try to set a maximum numeric value of val or the default value.
        :param val: value that should be changed to float
        :param str name: name of a config description option for logs
        :return: max(val, min_value) or unchanged value if it's not possible
        """
        try:
            return max(val, cls.max_opt[name])
        except (KeyError, ValueError):
            logger.warning('Cannot apply a minimum value to %r', name)
        return val
