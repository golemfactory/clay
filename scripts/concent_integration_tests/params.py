import itertools
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


def params_from_dict(d: dict) -> list:
    return list(
        itertools.chain.from_iterable(
            [(k, v) if v else (k, ) for k, v in d.items()]  # type: ignore
        )
    )


PROVIDER_RPC_PORT = os.environ.get('GOLEM_PROVIDER_RPC_PORT', '61001')
REQUESTOR_RPC_PORT = os.environ.get('GOLEM_REQUESTOR_RPC_PORT', '61000')

PROVIDER_PASSWORD = os.environ.get('GOLEM_PROVIDER_PASSWORD', 'dupa.8')
REQUESTOR_PASSWORD = os.environ.get('GOLEM_REQUESTOR_PASSWORD', 'dupa.8')

_REQUESTOR_ARGS = {
    '--concent': os.environ.get('GOLEM_CONCENT_VARIANT', 'staging'),
    '--datadir': get_datadir('requestor'),
    '--password': REQUESTOR_PASSWORD,
    '--accept-terms': None,
    '--rpc-address': 'localhost:%s' % REQUESTOR_RPC_PORT,
    '--protocol_id': '1337',
}
REQUESTOR_ARGS = params_from_dict(_REQUESTOR_ARGS)

_PROVIDER_ARGS = {
    '--concent': os.environ.get('GOLEM_CONCENT_VARIANT', 'staging'),
    '--datadir': get_datadir('provider'),
    '--password': PROVIDER_PASSWORD,
    '--accept-terms': None,
    '--rpc-address': 'localhost:%s' % PROVIDER_RPC_PORT,
    '--protocol_id': '1337',
}
PROVIDER_ARGS = params_from_dict(_PROVIDER_ARGS)

_PROVIDER_ARGS_DEBUG = {
    **_PROVIDER_ARGS,
    **{'--log-level': 'DEBUG'}
}
PROVIDER_ARGS_DEBUG = params_from_dict(_PROVIDER_ARGS_DEBUG)

_REQUESTOR_ARGS_DEBUG = {
    **_REQUESTOR_ARGS,
    **{'--log-level': 'DEBUG'}
}
REQUESTOR_ARGS_DEBUG = params_from_dict(_REQUESTOR_ARGS_DEBUG)

_REQUESTOR_ARGS_NO_CONCENT = dict(_REQUESTOR_ARGS_DEBUG)
_REQUESTOR_ARGS_NO_CONCENT['--concent'] = 'disabled'
REQUESTOR_ARGS_NO_CONCENT = params_from_dict(_REQUESTOR_ARGS_NO_CONCENT)

_PROVIDER_ARGS_NO_CONCENT = dict(_PROVIDER_ARGS_DEBUG)
_PROVIDER_ARGS_NO_CONCENT['--concent'] = 'disabled'
PROVIDER_ARGS_NO_CONCENT = params_from_dict(_PROVIDER_ARGS_NO_CONCENT)
