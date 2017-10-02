from golem.core.variables import APP_NAME, APP_VERSION

p2pconfig = {
    "discovery": {
        "listen_host": "0.0.0.0",
        "listen_port": 20171,
        "bootstrap_nodes": [
            b'enode://'
            b'b019bd3fad8ac41337b9fdd5d017caa33aec3779c5a0c7142a4073c17a6090dc'
            b'caa71333bd7fde9f5b7eeaebcffb1159fb59f08b0f70f9ebac463a263a7bc65d'
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
