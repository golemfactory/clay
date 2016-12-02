import logging

from autobahn.twisted import ApplicationSession
from autobahn.twisted.wamp import ApplicationRunner
from autobahn.wamp import types
from twisted.internet.defer import inlineCallbacks, Deferred, returnValue

logger = logging.getLogger('golem.rpc.client')


class RPCAddress(object):

    def __init__(self, protocol, host, port):
        self.protocol = protocol or 'tcp'
        self.host = host
        self.port = port
        self.address = u'{}://{}:{}'.format(self.protocol,
                                            self.host, self.port)

    def __str__(self):
        return str(self.address)

    def __unicode__(self):
        return self.address


class WebSocketAddress(RPCAddress):

    def __init__(self, host, port, realm, ssl=False):
        super(WebSocketAddress, self).__init__(u'wss' if ssl else u'ws', host, port)
        self.realm = realm


class SessionConnector(object):

    def __init__(self, session_class, address, extra=None, serializers=None, ssl=None,
                 proxy=None, headers=None, start_reactor=False, auto_reconnect=True, log_level='info'):

        self.session = session_class(realm=address.realm)
        self.address = address
        self.extra = extra
        self.serializers = serializers
        self.ssl = ssl
        self.proxy = proxy
        self.headers = headers
        self.log_level = log_level
        self.start_reactor = start_reactor
        self.auto_reconnect = auto_reconnect

    def connect(self):

        runner = ApplicationRunner(
            unicode(self.address),
            realm=self.address.realm,
            extra=self.extra,
            serializers=self.serializers,
            ssl=self.ssl,
            proxy=self.proxy,
            headers=self.headers
        )

        return runner.run(
            self.session,
            start_reactor=self.start_reactor,
            auto_reconnect=self.auto_reconnect,
            log_level=self.log_level
        )


class Session(ApplicationSession):

    def __init__(self, realm=u'golem'):
        self.ready = Deferred()
        self.config = types.ComponentConfig(realm=realm)
        self.methods = []
        self.events = []
        super(Session, self).__init__(self.config)

    @inlineCallbacks
    def onJoin(self, details):
        yield self.register_methods(self.methods)
        yield self.register_events(self.events)
        self.ready.callback(details)

    @inlineCallbacks
    def onLeave(self, details):
        if not self.ready.called:
            self.ready.errback(details or "Unknown error occured")

    @inlineCallbacks
    def register_methods(self, methods):
        for method, rpc_name in methods:
            yield self.register(method, rpc_name)
        returnValue(True)

    @inlineCallbacks
    def register_events(self, events):
        for method, rpc_name in events:
            yield self.subscribe(method, rpc_name)
        returnValue(True)


class Call(object):

    def __init__(self, session, method):
        self._session = session
        self._method = method

    def __call__(self, *args, **kwargs):
        return self._session.call(self._method, *args, **kwargs)


class Client(object):

    def __init__(self, session, method_map):
        self._session = session
        self._method_map = method_map

    def __getattribute__(self, name):
        if name.startswith('_'):
            return object.__getattribute__(self, name)
        return Call(self._session, self._method_map)


def object_method_map(obj, method_map):
    return [
        (getattr(obj, method_name), method_alias)
        for method_name, method_alias in method_map.items()
    ]
