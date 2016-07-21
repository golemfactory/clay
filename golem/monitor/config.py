MONITOR_HOST = "http://94.23.17.170:8881/"
MONITOR_REQUEST_TIMEOUT = 1.5
MONITOR_SENDER_THREAD_TIMEOUT = max(2.0, MONITOR_REQUEST_TIMEOUT)  # so that the queue does not get filled up

# Increase this number every time any change is made to the protocol (e.g. message object representation changes)
MONITOR_PROTO_VERSION = 0

