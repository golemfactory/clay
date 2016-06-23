import logging

from autobahn.twisted import WebSocketServerProtocol
from autobahn.twisted.wamp import ApplicationSession, ApplicationRunner
from autobahn.twisted.websocket import WebSocketServerFactory, WrappingWebSocketServerFactory
from twisted.internet.defer import inlineCallbacks

from golem.rpc.service import ServiceNameProxy, to_names_list, full_name, to_dict, full_method_name
from golem.rpc.wamp.router import WAMPRouter


logger = logging.getLogger(__name__)


class WebSocketAddress(object):
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.address = u'ws://{}:{}/golem'.format(host, port)

    def __str__(self):
        return str(self.address)

    def __unicode__(self):
        return self.address


class WebSocketListenInfo(object):
    def __init__(self, listen_info):
        self.listen_info = listen_info
        self.host = listen_info.getHost()
        self.port = self.host.port

        host = self.host.host

        if host == '0.0.0.0':
            host = '127.0.0.1'
        elif host == '::0':
            host = '::1'

        self.ws_address = WebSocketAddress(host, self.port)

    def __str__(self):
        return str(self.ws_address)

    def __unicode__(self):
        return self.ws_address


class WebSocketWAMPServerFactory(WrappingWebSocketServerFactory):
    def buildProtocol(self, addr):
        proto = WebSocketWAMPServerRouterProtocol()
        proto.factory = self
        proto._proto = self._factory.buildProtocol(addr)
        proto._proto.transport = proto
        return proto


class WebSocketWAMPServerRouterProtocol(WebSocketServerProtocol):
    def __init__(self, realm, options=None):
        super(WebSocketWAMPServerRouterProtocol, self).__init__()
        self.router = WAMPRouter(realm, options)


class WebSocketServer(object):

    @classmethod
    def listen(cls, port=0):
        from twisted.internet import reactor

        listen_info = reactor.listenTCP(port, WebSocketWAMPServerFactory())
        ws_listen_info = WebSocketListenInfo(listen_info)

        logger.debug("WebSocket RPC server listening on {}"
                     .format(ws_listen_info))

        return ws_listen_info


class WebSocketRPCInfo(object):
    def __init__(self, service, ws_address):
        self.full_service_name = full_name(service)
        self.method_names = to_names_list(service)
        self.ws_address = ws_address


class WebSocketRPCSession(ApplicationSession):

    def __init__(self, ws_address, keyring=None, config=None):
        super(WebSocketRPCSession, self).__init__(config)
        self.set_keyring(keyring)
        self.ws_address = ws_address
        self.rpc_info = None
        self.rpc_methods = {}
        self.joined = False

    def client(self, client_info):
        return _WebSocketRPCClient(self.call,
                                   client_info.full_service_name,
                                   client_info.method_names)

    @inlineCallbacks
    def onJoin(self, details):
        logger.debug("onJoin {}".format(details))
        self.joined = True
        self._register_service_methods()

    @inlineCallbacks
    def onLeave(self, details):
        logger.debug("onLeave {}".format(details))
        self.joined = False

    def register_service(self, service):
        self.rpc_info = WebSocketRPCInfo(service, self.ws_address)
        self.rpc_methods = to_dict(service)

        if self.joined:
            self._register_service_methods()

    def _register_service_methods(self):
        "Register service methods"
        if self.rpc_methods:
            for method_name, method in self.rpc_methods.iteritems():
                procedure = full_method_name(self.rpc_info.full_service_name, method_name)
                logger.debug("Register method {} as {}".format(method, procedure))
                self.register(method, procedure)
        else:
            logger.debug("No RPC methods to register")

    @staticmethod
    def create(ws_address, keyring=None, config=None):
        runner = ApplicationRunner(
            url=unicode(ws_address),
            realm=config.realm if config else u'Golem'
        )

        ws_rpc = WebSocketRPCSession(ws_address, keyring, config)
        deferred = runner.run(ws_rpc, start_reactor=False)
        return ws_rpc, deferred

    @staticmethod
    def on_success(*args, **kwargs):
        logger.info("Connection successful")

    @staticmethod
    def on_error(*args, **kwargs):
        logger.info("Connection error: {} {}".format(args, kwargs))


class _WebSocketRPCClient(ServiceNameProxy):

    name_exceptions = ServiceNameProxy.name_exceptions + \
                      ['full_service_name', 'full_method_name', 'call']

    def __init__(self, call_method, full_service_name, method_names):
        self.full_service_name = full_service_name
        self.call = call_method
        ServiceNameProxy.__init__(self, method_names)

    def full_method_name(self, method_name):
        return self.full_service_name + '.' + method_name

    def wrap(self, name, _):
        def wrapper(*args, **kwargs):
            return self.call(self.full_method_name(name), *args, **kwargs)
        return wrapper
