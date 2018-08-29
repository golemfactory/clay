import os
import tempfile


def get_datadir(role: str):
    env_key = 'GOLEM_{}_DATADIR'.format(role.upper())
    datadir = os.environ.get(env_key, None)
    if not datadir:
        datadir = tempfile.mkdtemp(prefix='golem-{}-'.format(role.lower()))
        os.environ[env_key] = datadir
    print("{} data directory: {}".format(role.capitalize(), datadir))
    return datadir


PROVIDER_RPC_PORT = os.environ.get('GOLEM_PROVIDER_RPC_PORT', '61001')
REQUESTOR_RPC_PORT = os.environ.get('GOLEM_REQUESTOR_RPC_PORT', '61000')

PROVIDER_PASSWORD = os.environ.get('GOLEM_PROVIDER_PASSWORD', 'dupa.8')
REQUESTOR_PASSWORD = os.environ.get('GOLEM_REQUESTOR_PASSWORD', 'dupa.8')

REQUESTOR_ARGS = [
    '--concent', os.environ.get('GOLEM_CONCENT_VARIANT', 'staging'),
    '--datadir', get_datadir('requestor'),
    '--password', REQUESTOR_PASSWORD,
    '--accept-terms',
    '--rpc-address', 'localhost:%s' % REQUESTOR_RPC_PORT,
    '--protocol_id', '1337',
]

PROVIDER_ARGS = [
    '--concent', os.environ.get('GOLEM_CONCENT_VARIANT', 'staging'),
    '--datadir', get_datadir('provider'),
    '--password', PROVIDER_PASSWORD,
    '--accept-terms',
    '--rpc-address', 'localhost:%s' % PROVIDER_RPC_PORT,
    '--protocol_id', '1337',
]

PROVIDER_ARGS_DEBUG = PROVIDER_ARGS + [
    '--log-level', 'DEBUG',
]

REQUESTOR_ARGS_DEBUG = REQUESTOR_ARGS + [
    '--log-level', 'DEBUG',
]

REQUESTOR_ARGS_NO_CONCENT = list(REQUESTOR_ARGS_DEBUG)
REQUESTOR_ARGS_NO_CONCENT[1] = 'disabled'

PROVIDER_ARGS_NO_CONCENT = list(PROVIDER_ARGS_DEBUG)
PROVIDER_ARGS_NO_CONCENT[1] = 'disabled'
