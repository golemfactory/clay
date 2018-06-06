PROVIDER_RPC_PORT = 61001
REQUESTOR_RPC_PORT = 61000

REQUESTOR_ARGS = [
    '--concent', 'staging',
    '--datadir', '/home/blue/golem-requestor',
    '--password', 'dupabladapsiakocia',
    '--accept-terms',
    '--rpc-address', 'localhost:%s' % REQUESTOR_RPC_PORT,
    #'--log-level', 'DEBUG',
    '--protocol_id', '1337',
]

PROVIDER_ARGS = [
    '--concent', 'staging',
    '--datadir', '/home/blue/golem-provider',
    '--password', 'dupabladapsiakocia',
    '--accept-terms',
    '--rpc-address', 'localhost:%s' % PROVIDER_RPC_PORT,
    #'--log-level', 'DEBUG',
    '--protocol_id', '1337',
]
