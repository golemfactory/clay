import multiprocessing
from collections import namedtuple

from ethereum.utils import denoms
from golem.appconfig import MIN_MEMORY_SIZE
from golem.interface.command import group, Argument, command, CommandHelper, CommandResult
from psutil import virtual_memory

Setting = namedtuple('Setting', ['help', 'type', 'converter', 'validator'])


def _int(x):
    return int(x)

_cpu_count = multiprocessing.cpu_count()
_virtual_mem = int(virtual_memory().total / 1024)


@group(help="Manage settings")
class Settings(object):

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
    requester = Argument(
        '--requester',
        optional=True,
        default=False,
        help="Show requester settings"
    )

    settings = {
        'node_name': Setting(
            'Node name',
            'non-empty string',
            lambda x: unicode(x) if isinstance(x, basestring) else None,
            lambda x: x and len(x) > 0
        ),
        'accept_task': Setting(
            'Accept tasks',
            'int {0, 1}',
            _int,
            lambda x: x in [0, 1]
        ),
        'max_resource_size': Setting(
            'Maximal resource size',
            'int > 0 [kB]',
            _int,
            lambda x: x > 0
        ),
        'use_waiting_for_task_timeout': Setting(
            'Use timeouts when waiting for tasks',
            'int {0, 1}',
            _int,
            lambda x: x in [0, 1]
        ),
        'waiting_for_task_timeout': Setting(
            'Timeout value to use when waiting for task',
            'int > 0 [s]',
            _int,
            lambda x: x > 0
        ),
        'getting_tasks_interval': Setting(
            'Interval between task requests',
            'int > 0 [s]',
            _int,
            lambda x: x > 0
        ),
        'getting_peers_interval': Setting(
            'Interval between peer requests',
            'int > 0 [s]',
            _int,
            lambda x: x > 0
        ),
        'task_session_timeout': Setting(
            'Task session timeout',
            'int > 0 [s]',
            _int,
            lambda x: x > 0
        ),
        'p2p_session_timeout': Setting(
            'P2P session timeout',
            'int > 0 [s]',
            _int,
            lambda x: x > 0
        ),
        'requesting_trust': Setting(
            'Minimal requester trust',
            'int [-100, 100]',
            _int,
            lambda x: -100 <= x <= 100
        ),
        'computing_trust': Setting(
            'Minimal provider trust',
            'int [-100, 100]',
            _int,
            lambda x: -100 <= x <= 100
        ),
        'min_price': Setting(
            'Min ETH/h price (provider)',
            'float >= 0',
            lambda x: float(x) * denoms.ether,
            lambda x: x >= 0
        ),
        'max_price': Setting(
            'Max ETH/h price (requester)',
            'float >= 0',
            lambda x: float(x) * denoms.ether,
            lambda x: x >= 0
        ),
        'use_ipv6': Setting(
            'Use IPv6',
            'int {0, 1}',
            _int,
            lambda x: x in [0, 1]
        ),
        'opt_peer_num': Setting(
            'Number of peers to keep',
            'int > 0',
            _int,
            lambda x: x > 0
        ),
        'send_pings': Setting(
            'Send ping messages to peers',
            'int {0, 1}',
            _int,
            lambda x: x in [0, 1]
        ),
        'pings_interval': Setting(
            'Interval between ping messages',
            'int > 0',
            _int,
            lambda x: x > 0
        ),
        'max_memory_size': Setting(
            'Max memory size',
            '{} > int >= {} [kB]'.format(_virtual_mem, MIN_MEMORY_SIZE),
            _int,
            lambda x: _virtual_mem > x >= MIN_MEMORY_SIZE
        ),
        'num_cores': Setting(
            'Number of CPU cores to use',
            '{} >= int >= 1'.format(_cpu_count),
            _int,
            lambda x: _cpu_count >= x >= 1
        )
    }

    settings_message = '\n'.join([
        '\t{:32} {:>32}\t{}'.format(k, s.type, s.help) for k, s in settings.iteritems()
    ])
    invalid_key_message =\
"""Invalid key

    Available settings:\n
""" + settings_message

    basic_settings = [
        'use_ipv6', 'opt_peer_num', 'getting_peers_interval', 'p2p_session_timeout', 'send_pings', 'pings_interval'
    ]

    requester_settings = [
        'max_price', 'computing_trust'
    ]

    key = Argument('key', help='Setting name', optional=True)
    value = Argument('value', help='Setting value', optional=True)

    @command(arguments=(basic, provider, requester), help="Show current settings")
    def show(self, basic, provider, requester):

        config = CommandHelper.wait_for(Settings.client.get_config())
        if not (basic ^ provider) and not (provider ^ requester):
            return config.__dict__

        result = dict()

        if basic:
            result.update({
                k: v for k, v in config.__dict__.iteritems()
                if k in Settings.basic_settings
            })

        if requester:
            result.update({
                k: v for k, v in config.__dict__.iteritems()
                if k in Settings.requester_settings
            })

        if provider:
            result.update({
                k: v for k, v in config.__dict__.iteritems()
                if k not in Settings.basic_settings and k not in Settings.requester_settings
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
            return CommandResult(error="Invalid value for {} (should be {}): {}".format(key, setting.type, exc))
        else:
            return CommandHelper.wait_for(Settings.client.update_setting(key, value))
