from golem.core.variables import APP_NAME, APP_VERSION

p2pconfig = {
    "discovery": {
        "listen_host": "0.0.0.0",
        "listen_port": 20171,
        "bootstrap_nodes": [
            b'enode://'
            b'2e139700d5284d8b0c1d9f6dba6515d476123e27130e8079a6905f8b76b07adf6'
            b'fd3dc5b618bc144caab30e338c5f8a48c4de5695ca9dfd3573904a1abe87ccb'
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
