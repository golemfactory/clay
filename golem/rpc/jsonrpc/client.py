import logging

import cPickle
from jsonrpc.proxy import JSONRPCProxy, ProxyEvents

from golem.rpc.service import ServiceNameProxy, to_names_list

logger = logging.getLogger(__name__)

RPCClient = ServiceNameProxy


class CustomJSONRPCProxy(JSONRPCProxy, ProxyEvents):

    def __init__(self, host, path='jsonrpc', serviceName=None, timeout=5,
                 *args, **kwargs):

        super(CustomJSONRPCProxy, self).__init__(host, path,
                                                 serviceName,
                                                 *args, **kwargs)
        self._eventhandler = self
        self.timeout = timeout

    def _post(self, url, data):
        return self._opener.open(url, data,
                                 timeout=self.timeout)

    def proc_response(self, data):
        print "RPC CALL {} {}".format(data, data.result)
        if data:
            if data.result:
                data.result = cPickle.loads(str(data.result))
        return data


class JsonRPCClient(RPCClient):

    name_exceptions = RPCClient.name_exceptions + ['rpc_proxy']

    def __init__(self, service_or_methods, url):
        if not isinstance(service_or_methods, list):
            service_or_methods = to_names_list(service_or_methods)

        self.rpc_proxy = CustomJSONRPCProxy(url, timeout=5)
        RPCClient.__init__(self, service_or_methods)

    def wrap(self, name, method):
        def wrapper(*args, **kwargs):
            return self.rpc_proxy.call(name, *args, **kwargs)
        return wrapper

    def __getattribute__(self, name, exceptions=None):
        return super(JsonRPCClient, self).__getattribute__(name,
                                                           JsonRPCClient.name_exceptions)


class JsonRPCClientBuilder(object):
    def __init__(self, service, url):
        self.method_names = to_names_list(service)
        self.url = url

    def build(self):
        return JsonRPCClient(self.method_names, self.url)
