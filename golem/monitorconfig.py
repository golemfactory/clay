# ###### Monitoring part ######

MONITOR_CONFIG = {
    'HOST': "http://94.23.17.170:8881/",
    #'HOST': "http://localhost:8881/",
    'REQUEST_TIMEOUT':  10,

    # Increase this number every time any change is made to the protocol (e.g. message object representation changes)
    'PROTO_VERSION': 0,
}
MONITOR_CONFIG['SENDER_THREAD_TIMEOUT'] = max(12, MONITOR_CONFIG['REQUEST_TIMEOUT'])  # so that the queue does not get filled up

try:
    from golem.monitorconfig_local import *
except ImportError:
    pass
