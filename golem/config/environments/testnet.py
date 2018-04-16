import os

from golem_sci.chains import RINKEBY

from golem.core.variables import PROTOCOL_CONST
from . import TESTNET

IS_MAINNET = False

# ETH

ETHEREUM_NODE_LIST = [
    'https://rinkeby.golem.network:55555',
    'http://188.165.227.180:55555',
    'http://94.23.17.170:55555',
    'http://94.23.57.58:55555',
]

ETHEREUM_CHAIN = RINKEBY
ETHEREUM_FAUCET_ENABLED = True

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
