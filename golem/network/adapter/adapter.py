import abc


class ClosedAdapterError(Exception):
    def __str__(self):
        return "Adapter's connection closed"


class Adapter(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def connect(self, host_info, **kwargs):
        return

    @abc.abstractmethod
    def send_resource(self, resource, **kwargs):
        return

    @abc.abstractmethod
    def get_resource(self, resource_info, **kwargs):
        return

    @abc.abstractmethod
    def close(self, **kwargs):
        return
