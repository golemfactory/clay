import os
import sys
from importlib import reload

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
