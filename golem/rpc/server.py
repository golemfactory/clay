import logging

import cPickle
from jsonrpc.server import ServerEvents, JSON_RPC
from twisted.web import server

from golem.rpc.service import ServiceMethods

logger = logging.getLogger(__name__)


class RPCServer(object):

    def __init__(self, service):
        self.service_methods = ServiceMethods(service)


class JsonRPCServer(ServerEvents, RPCServer):

    def __init__(self, service):
        ServerEvents.__init__(self, server)
        RPCServer.__init__(self, service)

        self.methods = self.service_methods.methods
        self._listen_info = None
        self._url = None

    def __call__(self, *args, **kwargs):
        return self

    def processrequest(self, result, args, **kw):
        print "RPC SERVER {} {} {}".format(result.__dict__, result.result, type(result.result))
        if result:
            if result.result:
                result.result = cPickle.dumps(result.result)
        return result

    @staticmethod
    def listen(service):
        json_rpc = JSON_RPC()
        json_rpc_server = JsonRPCServer(service)

        root = json_rpc.customize(json_rpc_server)
        site = server.Site(root)

        from twisted.internet import reactor
        json_rpc_server._listen_info = reactor.listenTCP(0, site)
        return json_rpc_server

    @property
    def url(self):
        if not self._url and self._listen_info:
            port = self._listen_info.getHost().port
            self._url = 'http://127.0.0.1:' + str(port)
        return self._url

