import multiprocessing
from collections import namedtuple
from types import FunctionType
from typing import Optional

from ethereum.utils import denoms
from golem.appconfig import MIN_MEMORY_SIZE
from golem.core.deferred import sync_wait
from golem.interface.command import group, Argument, command, CommandResult
from psutil import virtual_memory


_cpu_count = multiprocessing.cpu_count()
_virtual_mem = int(virtual_memory().total / 1024)


class Setting(namedtuple('Setting', ['help', 'type', 'converter', 'validator',
                                     'formatter'])):

    def __new__(cls, *args, formatter: Optional[FunctionType] = None):
        return super(Setting, cls).__new__(cls, *args, formatter)

    def format(self, value):
        if self.formatter:
            return self.formatter(value)
        return value


@group(help="Manage settings")
class Settings(object):
    BOOL_CONVERTIBLE_KEY_PREFIXES = [
        'accept_', 'debug_', 'use_', 'enable_',
        'in_shutdown', 'net_masking_enabled'
    ]

    client = None

    basic = Argument(
        '--basic',
        optional=True,
        default=False,
        help="Show basic settings"
    )
    provider = Argument(
        '--provider',
        optional=True,
        default=False,
        help="Show provider settings"
    )
    requestor = Argument(
        '--requestor',
        optional=True,
        default=False,
        help="Show requestor settings"
    )

    settings = {
        'node_name': Setting(
            'Node name',
            'non-empty string',
            lambda x: x if isinstance(x, str) else None,
            lambda x: x and len(x) > 0
        ),
        'accept_tasks': Setting(
            'Accept tasks',
            'flag {0, 1}',
            lambda x: bool(int(x)),
            lambda x: x in [True, False],
        ),
        'max_resource_size': Setting(
            'Maximal resource size',
            'int > 0 [kB]',
            int,
            lambda x: x > 0
        ),
        'getting_tasks_interval': Setting(
            'Interval between task requests',
            'int > 0 [s]',
            int,
            lambda x: x > 0
        ),
        'getting_peers_interval': Setting(
            'Interval between peer requests',
            'int > 0 [s]',
            int,
            lambda x: x > 0
        ),
        'task_session_timeout': Setting(
            'Task session timeout',
            'int > 0 [s]',
            int,
            lambda x: x > 0
        ),
        'p2p_session_timeout': Setting(
            'P2P session timeout',
            'int > 0 [s]',
            int,
            lambda x: x > 0
        ),
        'requesting_trust': Setting(
            'Minimal requestor trust',
            'float [-1., 1.]',
            float,
            lambda x: -1. <= x <= 1.
        ),
        'computing_trust': Setting(
            'Minimal provider trust',
            'float [-1., 1.]',
            float,
            lambda x: -1. <= x <= 1.
        ),
        'min_price': Setting(
            'Min GNT/h price (provider)',
            'float >= 0',
            lambda x: float(x) * denoms.ether,
            lambda x: float(x) >= 0,
            formatter=lambda x: float(x) / denoms.ether
        ),
        'max_price': Setting(
            'Max GNT/h price (requestor)',
            'float >= 0',
            lambda x: float(x) * denoms.ether,
            lambda x: float(x) >= 0,
            formatter=lambda x: float(x) / denoms.ether
        ),
        'use_ipv6': Setting(
            'Use IPv6',
            'flag {0, 1}',
            lambda x: bool(int(x)),
            lambda x: x in [True, False],
        ),
        'opt_peer_num': Setting(
            'Number of peers to keep',
            'int > 0',
            int,
            lambda x: x > 0
        ),
        'send_pings': Setting(
            'Send ping messages to peers',
            'flag {0, 1}',
            lambda x: bool(int(x)),
            lambda x: x in [True, False],
        ),
        'pings_interval': Setting(
            'Interval between ping messages',
            'int > 0',
            int,
            lambda x: x > 0
        ),
        'max_memory_size': Setting(
            'Max memory size',
            '{} > int >= {} [kB]'.format(_virtual_mem, MIN_MEMORY_SIZE),
            int,
            lambda x: _virtual_mem > x >= MIN_MEMORY_SIZE
        ),
        'num_cores': Setting(
            'Number of CPU cores to use',
            '{} >= int >= 1'.format(_cpu_count),
            int,
            lambda x: _cpu_count >= x >= 1
        ),
        'enable_talkback': Setting(
            'Enable error reporting with talkback service',
            'flag {0, 1}',
            lambda x: bool(int(x)),
            lambda x: x in [True, False],
        )
    }

    settings_message = '\n'.join([
        '\t{:32} {:>32}\t{}'.format(k, s.type, s.help)
        for k, s in settings.items()
    ])
    invalid_key_message =\
"""Invalid key

    Available settings:\n
""" + settings_message

    basic_settings = [
        'use_ipv6', 'opt_peer_num', 'getting_peers_interval',
        'p2p_session_timeout', 'send_pings', 'pings_interval'
    ]

    requestor_settings = [
        'max_price', 'computing_trust'
    ]

    key = Argument('key', help='Setting name', optional=True)
    value = Argument('value', help='Setting value', optional=True)

    @command(arguments=(basic, provider, requestor),
             help="Show current settings")
    def show(self, basic, provider, requestor):

        def fmt(k, v):
            if k in self.settings:
                return self.settings[k].format(v)
            return v

        def convert(k, v):
            if k in self.settings:
                return self.settings[k].converter(v)
            elif any(k.startswith(prefix) for prefix
                     in Settings.BOOL_CONVERTIBLE_KEY_PREFIXES):
                return bool(v)
            return v

        config = sync_wait(Settings.client.get_settings())
        config = {k: convert(k, v) for k, v in config.items()}
        config = {k: fmt(k, v) for k, v in config.items()}

        if not (basic ^ provider) and not (provider ^ requestor):
            return config

        result = dict()

        if basic:
            result.update({
                k: v for k, v in config.items()
                if k in Settings.basic_settings
            })

        if requestor:
            result.update({
                k: v for k, v in config.items()
                if k in Settings.requestor_settings
            })

        if provider:
            result.update({
                k: v for k, v in config.items()
                if k not in Settings.basic_settings
                and k not in Settings.requestor_settings
            })

        return result

    @command(arguments=(key, value), help="Change settings")
    def set(self, key, value):

        if not key or key not in Settings.settings:
            return CommandResult(error=Settings.invalid_key_message)

        setting = Settings.settings[key]

        try:

            value = setting.converter(value)
            if not setting.validator(value):
                raise Exception(value)

        except Exception as exc:
            return CommandResult(error="Invalid value for {} "
                                       "(should be {}): {}"
                                       .format(key, setting.type, exc))
        else:
            return sync_wait(Settings.client.update_setting(key, value))
