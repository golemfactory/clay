# ###### Monitoring part ######
# MONITOR_HOST = "http://94.23.17.170:8881/"


class MonitorConfig:

    MONITOR_HOST = "http://10.30.10.217:8080/stats/update"

    MONITOR_REQUEST_TIMEOUT = 10
    MONITOR_SENDER_THREAD_TIMEOUT = max(12, MONITOR_REQUEST_TIMEOUT)  # so that the queue does not get filled up

    # Increase this number every time any change is made to the protocol (e.g. message object representation changes)
    MONITOR_PROTO_VERSION = 0

    @classmethod
    def monitor_host(cls):
        return cls.MONITOR_HOST

    @classmethod
    def monitor_request_timeout(cls):
        return cls.MONITOR_REQUEST_TIMEOUT

    @classmethod
    def monitor_sender_thread_timeout(cls):
        return cls.MONITOR_SENDER_THREAD_TIMEOUT

    @classmethod
    def monitor_proto_version(cls):
        return cls.MONITOR_PROTO_VERSION


monitor_config = MonitorConfig()
