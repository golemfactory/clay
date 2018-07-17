import os
from typing import List

from golem_sci.chains import RINKEBY

from golem.core.variables import PROTOCOL_CONST
from . import TESTNET, CONCENT_ENVIRONMENT_VARIABLE

IS_MAINNET = False
ACTIVE_NET = TESTNET

# CORE

DATA_DIR = 'rinkeby'
ENABLE_TALKBACK = 1

# CONCENT

os.environ[CONCENT_ENVIRONMENT_VARIABLE] = os.environ.get(
    CONCENT_ENVIRONMENT_VARIABLE, 'test'
)


# ETH

class EthereumConfig:  # pylint:disable=too-few-public-methods
    NODE_LIST = [
        'https://rinkeby.golem.network:55555',
        'http://188.165.227.180:55555',
        'http://94.23.17.170:55555',
        'http://94.23.57.58:55555',
    ]

    FALLBACK_NODE_LIST: List[str] = [
    ]

    CHAIN = RINKEBY
    FAUCET_ENABLED = True

    WITHDRAWALS_ENABLED = False


# P2P

P2P_SEEDS = [
    ('94.23.57.58', 40102),
    ('94.23.57.58', 40104),
    ('94.23.196.166', 40102),
    ('94.23.196.166', 40104),
    ('188.165.227.180', 40102),
    ('188.165.227.180', 40104),
    ('seeds.test.golem.network', 40102),
    ('seeds.test.golem.network', 40104),
]

PROTOCOL_CONST.POSTFIX = '-' + TESTNET
PROTOCOL_CONST.patch_protocol_id(value=PROTOCOL_CONST.NUM)

# APPS

APP_MANAGER_CONFIG_FILES = [
    os.path.join('apps', 'registered.ini'),
    os.path.join('apps', 'registered_test.ini')
]

# MONITOR

SEND_PAYMENT_INFO_TO_MONITOR = True
