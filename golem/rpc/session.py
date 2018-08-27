import logging

from autobahn.twisted import ApplicationSession
from autobahn.twisted.websocket import WampWebSocketClientFactory
from autobahn.wamp import ProtocolError
from autobahn.wamp import types
from twisted.application.internet import ClientService, backoffPolicy
from twisted.internet import ssl as twisted_ssl
from twisted.internet._sslverify import optionsForClientTLS  # noqa # pylint: disable=protected-access
from twisted.internet.defer import inlineCallbacks, Deferred
from twisted.internet.endpoints import (
    TCP4ClientEndpoint, TCP6ClientEndpoint, SSL4ClientEndpoint
)

from golem.rpc.common import X509_COMMON_NAME

logger = logging.getLogger('golem.rpc')


OPEN_HANDSHAKE_TIMEOUT = 30.
CLOSE_HANDSHAKE_TIMEOUT = 10.
AUTO_PING_INTERVAL = 15.
AUTO_PING_TIMEOUT = 12.
BACKOFF_POLICY_FACTOR = 1.2


class RPCAddress(object):

    def __init__(self, protocol, host, port):
        self.protocol = protocol
        self.host = host
        self.port = port
        self.address = '{}://{}:{}'.format(self.protocol,
                                           self.host, self.port)

    def __str__(self):
        return str(self.address)

    def __unicode__(self):
        return self.address


class WebSocketAddress(RPCAddress):

    def __init__(self, host, port, realm, ssl=True):
        self.realm = str(realm)
        self.ssl = ssl

        protocol = 'wss' if ssl else 'ws'
        super(WebSocketAddress, self).__init__(protocol, host, port)


class Session(ApplicationSession):

    def __init__(self, address, methods=None, events=None,  # noqa # pylint: disable=too-many-arguments
                 cert_manager=None, use_ipv6=False) -> None:

        self.address = address
        self.methods = methods or []
        self.events = events or []
        self.subs = {}

        self.ready = Deferred()
        self.connected = False

        self._cert_manager = cert_manager

        self._client = None
        self._reconnect_service = None
        self._use_ipv6 = use_ipv6

        self.config = types.ComponentConfig(realm=address.realm)
        super(Session, self).__init__(self.config)

    def connect(self, auto_reconnect=True):

        def init(proto):
            reactor.addSystemEventTrigger('before', 'shutdown', cleanup, proto)
            return proto

        def cleanup(proto):
            session = getattr(proto, '_session', None)
            if session is None:
                return
            if session.is_attached():
                return session.leave()
            elif session.is_connected():
                return session.disconnect()

        from twisted.internet import reactor

        transport_factory = WampWebSocketClientFactory(self, str(self.address))
        transport_factory.setProtocolOptions(
            maxFramePayloadSize=1048576,
            maxMessagePayloadSize=1048576,
            autoFragmentSize=65536,
            failByDrop=False,
            openHandshakeTimeout=OPEN_HANDSHAKE_TIMEOUT,
            closeHandshakeTimeout=CLOSE_HANDSHAKE_TIMEOUT,
            tcpNoDelay=True,
            autoPingInterval=AUTO_PING_INTERVAL,
            autoPingTimeout=AUTO_PING_TIMEOUT,
            autoPingSize=4,
        )

        if self.address.ssl:
            if self._cert_manager:
                cert_data = self._cert_manager.read_certificate()
                authority = twisted_ssl.Certificate.loadPEM(cert_data)
            else:
                authority = None

            context_factory = optionsForClientTLS(X509_COMMON_NAME,
                                                  trustRoot=authority)
            self._client = SSL4ClientEndpoint(reactor,
                                              self.address.host,
                                              self.address.port,
                                              context_factory)
        else:
            if self._use_ipv6:
                endpoint_cls = TCP6ClientEndpoint
            else:
                endpoint_cls = TCP4ClientEndpoint

            self._client = endpoint_cls(reactor,
                                        self.address.host,
                                        self.address.port)

        if auto_reconnect:
            self._reconnect_service = ClientService(
                endpoint=self._client,
                factory=transport_factory,
                retryPolicy=backoffPolicy(factor=BACKOFF_POLICY_FACTOR)
            )
            self._reconnect_service.startService()
            deferred = self._reconnect_service.whenConnected()
        else:
            deferred = self._client.connect(transport_factory)

        deferred.addCallback(init)
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

    def onDisconnect(self):
        self.connected = False
        super(Session, self).onDisconnect()

    @inlineCallbacks
    def add_methods(self, methods):
        self.methods += methods
        yield self.register_methods(methods)

    @inlineCallbacks
    def register_methods(self, methods):
        for method, rpc_name in methods:
            deferred = self.register(method, str(rpc_name))
            deferred.addErrback(self._on_error)
            yield deferred

    @inlineCallbacks
    def register_events(self, events):
        for method, rpc_name in events:
            deferred = self.subscribe(method, str(rpc_name))
            deferred.addErrback(self._on_error)
            self.subs[rpc_name] = yield deferred

    @inlineCallbacks
    def unregister_events(self, event_names):
        for event_name in event_names:
            if event_name in self.subs:
                yield self.subs[event_name].unsubscribe()
                self.subs.pop(event_name, None)
            else:
                logger.error("RPC: Not subscribed to: {}".format(event_name))

    def is_open(self):
        return self.connected and self.is_attached() and not self.is_closing()

    def is_closing(self):
        return self._goodbye_sent or self._transport_is_closing

    @staticmethod
    def _on_error(err):
        logger.error("RPC: Session error: {}".format(err))
        return err


class Client(object):

    def __init__(self, session, method_map, timeout=2):

        self._session = session
        self._timeout = timeout

        for method_name, method_alias in list(method_map.items()):
            setattr(self, method_name, self._make_call(method_alias))

    def _make_call(self, method_alias):
        return lambda *a, **kw: self._call(str(method_alias), *a, **kw)

    def _call(self, method_alias, *args, **kwargs):
        if self._session.is_open():
            deferred = self._session.call(str(method_alias),
                                          *args, **kwargs)
            deferred.addErrback(self._on_error)
        else:
            deferred = Deferred()
            if not self._session.is_closing():
                deferred.errback(ProtocolError("RPC: session is not "
                                               "yet established"))
        return deferred

    def _on_error(self, err):
        if not self._session.is_closing():
            logger.error("RPC: call error: {}".format(err))
            return err


class Publisher(object):

    def __init__(self, session):
        self.session = session

    def publish(self, event_alias, *args, **kwargs):
        if self.session.is_open():
            self.session.publish(str(event_alias), *args, **kwargs)
        elif not self.session.is_closing():
            logger.warning("RPC: Cannot publish '{}', "
                           "session is not yet established"
                           .format(event_alias))


def object_method_map(obj, method_map):
    return [
        (getattr(obj, method_name), method_alias)
        for method_name, method_alias in list(method_map.items())
    ]
