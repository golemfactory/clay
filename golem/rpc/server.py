import logging

import jsonrpc
from jsonrpc.server import ServerEvents, JSON_RPC
from twisted.web import server

from golem.rpc.service import ServiceMethods

logger = logging.getLogger(__name__)


class RPCServer(object):

    def __init__(self, service):
        self.service_methods = ServiceMethods(service)


# class _JSON_RPC(JSON_RPC):
#     def _cbRender(self, result, request):
#         @self.eventhandler.defer
#         def _inner(*args, **_):
#             code = self.eventhandler.getresponsecode(result)
#             request.setResponseCode(code)
#             self.eventhandler.log(result, request, error=False)
#             if result is not None:
#                 request.setHeader("content-type", 'application/json')
#                 result_ = jsonrpc.jsonutil.encode(result).encode('utf-8')
#                 request.setHeader("content-length", len(result_))
#                 request.write(result_)
#             request.notifyFinish()
#
#         return _inner
#
#     def _ebRender(self, result, request, id, finish=True):
#         @self.eventhandler.defer
#         def _inner(*args, **_):
#             err = None
#             if not isinstance(result, BaseException):
#                 try:
#                     result.raiseException()
#                 except BaseException, e:
#                     err = e
#                     self.eventhandler.log(err, request, error=True)
#             else:
#                 err = result
#             err = self.render_error(err, id)
#
#             code = self.eventhandler.getresponsecode(result)
#             request.setResponseCode(code)
#
#             request.setHeader("content-type", 'application/json')
#             result_ = jsonrpc.jsonutil.encode(err).encode('utf-8')
#             request.setHeader("content-length", len(result_))
#             request.write(result_)
#             if finish:
#                 request.notifyFinish()
#
#         return _inner


class JsonRPCServer(ServerEvents, RPCServer):

    def __init__(self, service):
        ServerEvents.__init__(self, server)
        RPCServer.__init__(self, service)

        self.methods = self.service_methods.methods
        self._listen_info = None
        self._url = None

    def __call__(self, *args, **kwargs):
        return self

    def log(self, responses, txrequest, error=False):
        if isinstance(responses, list):
            for response in responses:
                msg = self._get_msg(response)
                logger.debug('{} {} {}'.format(txrequest.code, txrequest, msg))
        else:
            msg = self._get_msg(responses)
            logger.debug('{} {} {}'.format(txrequest.code, txrequest, msg))

    def _get_msg(self, response):
        return ' '.join(str(x) for x in [response.id, response.result or response.error])

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
