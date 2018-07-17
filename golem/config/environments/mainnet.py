import os

from golem_sci.chains import MAINNET

from golem.core.variables import PROTOCOL_CONST
from . import CONCENT_ENVIRONMENT_VARIABLE

IS_MAINNET = True
ACTIVE_NET = MAINNET

# CORE

DATA_DIR = 'mainnet'
ENABLE_TALKBACK = 0

# CONCENT

os.environ[CONCENT_ENVIRONMENT_VARIABLE] = os.environ.get(
    CONCENT_ENVIRONMENT_VARIABLE, 'disabled'
)


# ETH

class EthereumConfig:  # pylint:disable=too-few-public-methods
    NODE_LIST = [
        'https://geth.golem.network:55555',
        'https://0.geth.golem.network:55555',
        'https://1.geth.golem.network:55555',
        'https://2.geth.golem.network:55555',
        'https://geth.golem.network:2137',
        'https://0.geth.golem.network:2137',
        'https://1.geth.golem.network:2137',
        'https://2.geth.golem.network:2137',
    ]

    FALLBACK_NODE_LIST = [
        'https://proxy.geth.golem.network:2137',
    ]

    CHAIN = MAINNET
    FAUCET_ENABLED = False

    WITHDRAWALS_ENABLED = True


# P2P

P2P_SEEDS = [
    ('seeds.golem.network', 40102),
    ('0.seeds.golem.network', 40102),
    ('1.seeds.golem.network', 40102),
    ('2.seeds.golem.network', 40102),
    ('3.seeds.golem.network', 40102),
    ('4.seeds.golem.network', 40102),
    ('5.seeds.golem.network', 40102),
    ('proxy.seeds.golem.network', 40102),
]

PROTOCOL_CONST.POSTFIX = ''
PROTOCOL_CONST.patch_protocol_id(value=PROTOCOL_CONST.NUM)

# APPS

APP_MANAGER_CONFIG_FILES = [
    os.path.join('apps', 'registered.ini')
]

# MONITOR

SEND_PAYMENT_INFO_TO_MONITOR = False
