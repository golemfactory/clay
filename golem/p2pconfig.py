from golem.core.variables import APP_NAME, APP_VERSION

p2pconfig = {
    "discovery": {
        "listen_host": "0.0.0.0",
        "listen_port": 20171,
        "bootstrap_nodes": [
            b'enode://'
            b'a9ac7cb82f08929e3253372b0c7fab7589fd37c9ee5cc2ad1cc9da75ffa8b7839'
            b'8450aa5a25f1836d4984700570f69aa8356a94ca9bd55c5d226d051c5bd6742'
            b'@94.23.17.170:20171'
        ]
    },
    "p2p": {
        "listen_host": "0.0.0.0",
        "listen_port": 20171,
        "min_peers": 3,
        "max_peers": 15
    },
    "log_disconnects": True,
    "client_version_string": '{} {}'.format(APP_NAME, APP_VERSION)
}
