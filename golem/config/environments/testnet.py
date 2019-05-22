import os
from typing import List

from golem_sci import contracts
from golem_sci.chains import RINKEBY

from golem.core.variables import PROTOCOL_CONST, CONCENT_CHOICES
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

class EthereumConfig:
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

    CONTRACT_ADDRESSES = {
        contracts.GNT: '0x924442A66cFd812308791872C4B242440c108E19',
        contracts.GNTB: '0x123438d379BAbD07134d1d4d7dFa0BCbd56ca3F3',
        contracts.Faucet: '0x77b6145E853dfA80E8755a4e824c4F510ac6692e',
    }

    deposit_contract_address = CONCENT_CHOICES[
        os.environ[CONCENT_ENVIRONMENT_VARIABLE]
    ].get('deposit_contract_address')

    if deposit_contract_address:
        CONTRACT_ADDRESSES[contracts.GNTDeposit] = deposit_contract_address

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
