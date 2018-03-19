# ###### Monitoring part ######

MONITOR_CONFIG = {
    'HOST': "https://stats.golem.network/",
    'REQUEST_TIMEOUT': 10,

    # Increase this number every time any change is made to the protocol
    # (e.g. message object representation changes)
    'PROTO_VERSION': 1,
}

# so that the queue will not get filled up
MONITOR_CONFIG['SENDER_THREAD_TIMEOUT'] = max(
    12,
    MONITOR_CONFIG['REQUEST_TIMEOUT']
)

try:
    from golem.monitorconfig_local import *  # noqa
except ImportError:
    pass
