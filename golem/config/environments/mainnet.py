import os

from golem_sci import contracts
from golem_sci.chains import MAINNET

from golem.core.variables import PROTOCOL_CONST, CONCENT_CHOICES
from . import CONCENT_ENVIRONMENT_VARIABLE


# CORE

DATA_DIR = 'mainnet'
ENABLE_TALKBACK = 0

# ETH


class EthereumConfig:
    def __init__(self):
        self.IS_MAINNET = True
        self.ACTIVE_NET = MAINNET
        self.NODE_LIST = [
            'https://geth.golem.network:55555',
            'https://0.geth.golem.network:55555',
            'https://1.geth.golem.network:55555',
            'https://2.geth.golem.network:55555',
            'https://geth.golem.network:2137',
            'https://0.geth.golem.network:2137',
            'https://1.geth.golem.network:2137',
            'https://2.geth.golem.network:2137',
        ]

        self.FALLBACK_NODE_LIST = [
            'https://proxy.geth.golem.network:2137',
        ]

        self.CHAIN = MAINNET
        self.FAUCET_ENABLED = False

        self.CONTRACT_ADDRESSES = {
            contracts.GNT: '0xa74476443119A942dE498590Fe1f2454d7D4aC0d',
            contracts.GNTB: '0xA7dfb33234098c66FdE44907e918DAD70a3f211c',
        }

        os.environ[CONCENT_ENVIRONMENT_VARIABLE] = os.environ.get(
            CONCENT_ENVIRONMENT_VARIABLE, 'disabled'
        )

        self.CONCENT_VARIANT = CONCENT_CHOICES[
            os.environ.get(CONCENT_ENVIRONMENT_VARIABLE, 'disabled')
        ]

        self.WITHDRAWALS_ENABLED = True


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

CONCENT_SUPPORTED_APPS = (
    'blender',
    'blender_nvgpu'
)

TASK_API_IMG_NAMES = []
