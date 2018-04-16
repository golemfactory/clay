import os

from golem_sci.chains import MAINNET

from golem.core.variables import PROTOCOL_CONST

IS_MAINNET = True

# ETH

ETHEREUM_NODE_LIST = [
    'https://geth.golem.network:55555',
    'https://0.geth.golem.network:55555',
    'https://1.geth.golem.network:55555',
    'https://2.geth.golem.network:55555',
]

ETHEREUM_CHAIN = MAINNET
ETHEREUM_FAUCET_ENABLED = False

# P2P

P2P_SEEDS = [
    ('seeds.golem.network', 40102),
]

PROTOCOL_CONST.POSTFIX = ''
PROTOCOL_CONST.patch_protocol_id(value=PROTOCOL_CONST.NUM)

# APPS

APP_MANAGER_CONFIG_FILES = [
    os.path.join('apps', 'registered.ini')
]
