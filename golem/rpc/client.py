import logging

from jsonrpc.proxy import JSONRPCProxy

from golem.rpc.service import ServiceProxy

logger = logging.getLogger(__name__)


class RPCClient(ServiceProxy):
    def __init__(self, service, url):
        ServiceProxy.__init__(self, service, self.wrap)
        self.url = url

    def wrap(self, name, method):
        raise NotImplementedError()


class JsonRPCClient(RPCClient):

    name_exceptions = ServiceProxy.name_exceptions + ['wrap', 'proxy']

    def __init__(self, service, url):
        self.proxy = JSONRPCProxy(url, path='/')
        RPCClient.__init__(self, service, url)

    def wrap(self, name, method):
        def wrapper(*args, **kwargs):
            logger.debug("RPC call {} {} {}".format(name, args, kwargs))
            return self.proxy.call(name, *args, **kwargs)
        return wrapper

    def __getattribute__(self, name, exceptions=None):
        return super(JsonRPCClient, self).__getattribute__(name,
                                                           JsonRPCClient.name_exceptions)




