import os
from typing import List

from golem_sci import contracts
from golem_sci.chains import MAINNET
from golem_task_api.envs import DOCKER_CPU_ENV_ID, DOCKER_GPU_ENV_ID

from golem.core.variables import PROTOCOL_CONST
from . import CONCENT_ENVIRONMENT_VARIABLE, init_concent_config


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
            CONCENT_ENVIRONMENT_VARIABLE, 'main'
        )

        init_concent_config(self)

        self.WITHDRAWALS_ENABLED = True


# P2P

BROADCAST_PUBKEY = b'\xab\xab;\xb0\x89\x10\r\xf8Hs\xd7\x91\xcc\x13\xdb\x0b9tw\x80\xd4t?\xdc\x9dS.\x9at\xe3X\xbcBK\x1c\xef\xdb3\xab}z\xad\xde"ZW\xa9T\xdeN\xb6\xc7P\x0e\xa9\x7fv\x1a\xec\xcbN\x07R\x10'  # noqa pylint: disable=line-too-long

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

TASK_API_ENVS: List[str] = [
    DOCKER_CPU_ENV_ID, DOCKER_GPU_ENV_ID
]
