# ###### Monitoring part ######

MONITOR_CONFIG = {
    'HOST': "https://stats.golem.network/",
    'PING_ME_HOSTS': [
        "http://ports.golem.network/",
        "https://stats.golem.network/",
    ],
    'REQUEST_TIMEOUT': 10,
    'PING_INTERVAL': 1000,

    # Increase this number every time any change is made to the protocol
    # (e.g. message object representation changes)
    'PROTO_VERSION': 2,
}

# so that the queue will not get filled up
MONITOR_CONFIG['SENDER_THREAD_TIMEOUT'] = max(
    60,
    MONITOR_CONFIG['REQUEST_TIMEOUT']
)

# load local configuration if present
try:
    from golem.monitorconfig_local import MONITOR_CONFIG as MONITOR_CONFIG_LOCAL
    MONITOR_CONFIG.update(MONITOR_CONFIG_LOCAL)
except ImportError:
    pass
