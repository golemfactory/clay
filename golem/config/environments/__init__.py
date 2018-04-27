import os

GOLEM_ENVIRONMENT_VARIABLE = 'GOLEM_ENVIRONMENT'
CONCENT_ENVIRONMENT_VARIABLE = 'CONCENT_ENVIRONMENT'
TESTNET = 'testnet'


def set_environment(net: str, concent: str) -> None:
    if net:
        os.environ[GOLEM_ENVIRONMENT_VARIABLE] = net
    if concent:
        os.environ[CONCENT_ENVIRONMENT_VARIABLE] = concent

    elif not os.environ.get(GOLEM_ENVIRONMENT_VARIABLE):
        os.environ[GOLEM_ENVIRONMENT_VARIABLE] = TESTNET
