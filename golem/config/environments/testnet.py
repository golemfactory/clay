import os
from typing import List

from golem_sci import contracts
from golem_sci.chains import RINKEBY
from golem_task_api.envs import DOCKER_CPU_ENV_ID, DOCKER_GPU_ENV_ID

from golem.core.variables import PROTOCOL_CONST
from . import TESTNET, CONCENT_ENVIRONMENT_VARIABLE, init_concent_config

# CORE

DATA_DIR = 'rinkeby'
ENABLE_TALKBACK = 1

# ETH

# todo FIXME before 0.21 release
# https://github.com/golemfactory/golem/issues/4254
# this class and actually, `golem.config` in general
# need to be refactored to remove reliance on system environment variables


class EthereumConfig:  # pylint:disable=too-many-instance-attributes
    def __init__(self):
        self.IS_MAINNET = False
        self.ACTIVE_NET = TESTNET
        self.NODE_LIST = [
            'https://0.geth.testnet.golem.network:55555',
            'http://1.geth.testnet.golem.network:55555',
            'http://2.geth.testnet.golem.network:55555',
            'http://3.geth.testnet.golem.network:55555',
        ]

        self.FALLBACK_NODE_LIST: List[str] = [
        ]

        self.CHAIN = RINKEBY
        self.FAUCET_ENABLED = True

        self.CONTRACT_ADDRESSES = {
            contracts.GNT: '0x924442A66cFd812308791872C4B242440c108E19',
            contracts.GNTB: '0x123438d379BAbD07134d1d4d7dFa0BCbd56ca3F3',
            contracts.Faucet: '0x77b6145E853dfA80E8755a4e824c4F510ac6692e',
        }

        os.environ[CONCENT_ENVIRONMENT_VARIABLE] = os.environ.get(
            CONCENT_ENVIRONMENT_VARIABLE, 'test'
        )

        init_concent_config(self)

        self.WITHDRAWALS_ENABLED = False


# P2P

BROADCAST_PUBKEY = b'\xbe\x0e\xb0@\xad\xad~\xd7\xe3\xca\x96*k\x7f\x0b*\x96++\xb0{\x95+n~\xfdF\xc8\x88\xff\x06\x93cr\xb3\xcb@\xc8Y\xd5n\x98|\xec\x90$\xf2E\xf9\xbbyh:\x99"\xaf\xa2-\xc9os:\xb6\x88'  # noqa pylint: disable=line-too-long

P2P_SEEDS = [
    ('0.seeds.testnet.golem.network', 40102),
    ('0.seeds.testnet.golem.network', 40104),
    ('1.seeds.testnet.golem.network', 40102),
    ('1.seeds.testnet.golem.network', 40104),
    ('2.seeds.testnet.golem.network', 40102),
    ('2.seeds.testnet.golem.network', 40104),
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

CONCENT_SUPPORTED_APPS = (
    'blender',
    'blender_nvgpu'
)

TASK_API_ENVS = [
    DOCKER_CPU_ENV_ID, DOCKER_GPU_ENV_ID
]
