import os
import sys
from importlib import reload

from golem_sci import contracts
from golem.core.variables import CONCENT_CHOICES

GOLEM_ENVIRONMENT_VARIABLE = 'GOLEM_ENVIRONMENT'
CONCENT_ENVIRONMENT_VARIABLE = 'CONCENT_ENVIRONMENT'
TESTNET = 'testnet'


def set_environment(net: str, concent: str) -> None:
    if net:
        os.environ[GOLEM_ENVIRONMENT_VARIABLE] = net
    if concent:
        os.environ[CONCENT_ENVIRONMENT_VARIABLE] = concent

    if 'golem.config.active' in sys.modules:
        reload(sys.modules['golem.config.active'])


def init_concent_config(config):
    config.CONCENT_VARIANT = CONCENT_CHOICES[
        os.environ.get(CONCENT_ENVIRONMENT_VARIABLE, 'disabled')
    ]

    config.deposit_contract_address = \
        config.CONCENT_VARIANT.get('deposit_contract_address')

    if config.deposit_contract_address:
        config.CONTRACT_ADDRESSES[contracts.GNTDeposit] = \
            config.deposit_contract_address
