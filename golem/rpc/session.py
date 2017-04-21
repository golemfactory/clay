import logging

from autobahn.twisted import ApplicationSession
from autobahn.twisted.wamp import ApplicationRunner
from autobahn.twisted.websocket import WampWebSocketClientFactory
from autobahn.wamp import ProtocolError
from autobahn.wamp import types
from twisted.internet.defer import inlineCallbacks, Deferred

logger = logging.getLogger('golem.rpc')


setProtocolOptions = WampWebSocketClientFactory.setProtocolOptions


def set_protocol_options(instance, **options):
    options['autoPingInterval'] = 5.
    options['autoPingTimeout'] = 15.
    options['openHandshakeTimeout'] = 30.
    setProtocolOptions(instance, **options)

# monkey-patch setProtocolOptions and provide custom values
WampWebSocketClientFactory.setProtocolOptions = set_protocol_options


class RPCAddress(object):

    def __init__(self, protocol, host, port):
        self.protocol = protocol
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
        self.realm = unicode(realm)
        self.ssl = ssl

        protocol = u'wss' if ssl else u'ws'
        super(WebSocketAddress, self).__init__(protocol, host, port)


class Session(ApplicationSession):

    def __init__(self, address, methods=None, events=None):
        self.address = address
        self.methods = methods or []
        self.events = events or []
        self.subs = {}

        self.ready = Deferred()
        self.connected = False

        self.config = types.ComponentConfig(realm=address.realm)
        super(Session, self).__init__(self.config)

    def connect(self, ssl=None, proxy=None, headers=None, auto_reconnect=True, log_level='info'):
        runner = ApplicationRunner(
            url=unicode(self.address),
            realm=self.address.realm,
            ssl=ssl,
            proxy=proxy,
            headers=headers
        )

        deferred = runner.run(
            make=self,
            start_reactor=False,
            auto_reconnect=auto_reconnect,
            log_level=log_level
        )

        deferred.addErrback(self.ready.errback)
        return self.ready

    @inlineCallbacks
    def onJoin(self, details):
        yield self.register_methods(self.methods)
        yield self.register_events(self.events)
        self.connected = True
        if not self.ready.called:
            self.ready.callback(details)

    def onLeave(self, details):
        self.connected = False
        if not self.ready.called:
            self.ready.errback(details or "Unknown error occurred")
        super(Session, self).onLeave(details)

    @inlineCallbacks
    def register_methods(self, methods):
        for method, rpc_name in methods:
            deferred = self.register(method, unicode(rpc_name))
            deferred.addErrback(self._on_error)
            yield deferred

    @inlineCallbacks
    def register_events(self, events):
        for method, rpc_name in events:
            deferred = self.subscribe(method, unicode(rpc_name))
            deferred.addErrback(self._on_error)
            self.subs[rpc_name] = yield deferred

    @inlineCallbacks
    def unregister_events(self, event_names):
        for event_name in event_names:
            if event_name in self.subs:
                yield self.subs[event_name].unsubscibe()
                self.subs.pop(event_name, None)
            else:
                logger.error("RPC: Not subscribed to: {}".format(event_name))

    @staticmethod
    def _on_error(err):
        logger.error("RPC: Session error: {}".format(err))


class Client(object):

    def __init__(self, session, method_map, timeout=2):

        self._session = session
        self._timeout = timeout

        for method_name, method_alias in method_map.items():
            setattr(self, method_name, self._make_call(method_alias))

    def _make_call(self, method_alias):
        return lambda *a, **kw: self._call(unicode(method_alias), *a, **kw)

    def _call(self, method_alias, *args, **kwargs):
        if self._session.connected:
            # if 'options' not in kwargs or not kwargs.get('options'):
            #     kwargs['options'] = types.CallOptions(timeout=self.timeout)
            deferred = self._session.call(unicode(method_alias), *args, **kwargs)
            deferred.addErrback(self._on_error)
        else:
            deferred = Deferred()
            deferred.errback(ProtocolError("RPC: session is not yet established"))

        return deferred

    @staticmethod
    def _on_error(err):
        logger.error("RPC: call error: {}".format(err))
        raise err


class Publisher(object):

    def __init__(self, session):
        self.session = session

    def publish(self, event_alias, *args, **kwargs):
        if self.session.connected:
            self.session.publish(unicode(event_alias), *args, **kwargs)
        else:
            logger.warn("RPC: Cannot publish '{}', session is not yet established"
                        .format(event_alias))


def object_method_map(obj, method_map):
    return [
        (getattr(obj, method_name), method_alias)
        for method_name, method_alias in method_map.items()
    ]
