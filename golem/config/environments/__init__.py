import os

ENVIRONMENT_VARIABLE = 'GOLEM_ENVIRONMENT'
TESTNET = 'testnet'


def set_environment(net: str) -> None:
    if net:
        os.environ[ENVIRONMENT_VARIABLE] = net

    elif not os.environ.get(ENVIRONMENT_VARIABLE):
        os.environ[ENVIRONMENT_VARIABLE] = TESTNET
