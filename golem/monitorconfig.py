# ###### Monitoring part ######

MONITOR_CONFIG = {
    'HOST': "https://stats.golem.network/",
    'PING_ME_HOSTS': [
        "http://ports.golem.network/",
        "https://stats.golem.network/",
    ],
    'REQUEST_TIMEOUT': 10,

    # Increase this number every time any change is made to the protocol
    # (e.g. message object representation changes)
    'PROTO_VERSION': 1,
}

try:
    from golem.monitorconfig_local import *  # noqa
except ImportError:
    pass
