from golem.core.variables import APP_NAME, APP_VERSION

p2pconfig = {
    "discovery": {
        "listen_host": "0.0.0.0",
        "listen_port": 20171,
        "bootstrap_nodes": []
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
