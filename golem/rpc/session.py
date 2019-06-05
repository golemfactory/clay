import functools
import logging
import typing

from netaddr import IPAddress, valid_ipv4
from autobahn.twisted import ApplicationSession
from autobahn.twisted.websocket import WampWebSocketClientFactory
from autobahn.wamp import Error as WampError, ProtocolError, auth
from autobahn.wamp import types
from twisted.application.internet import ClientService, backoffPolicy
from twisted.internet import ssl as twisted_ssl
from twisted.internet._sslverify import optionsForClientTLS  # noqa # pylint: disable=protected-access
from twisted.internet.defer import inlineCallbacks, Deferred
from twisted.internet.endpoints import (
    TCP4ClientEndpoint, TCP6ClientEndpoint, SSL4ClientEndpoint
)

from golem.rpc.common import X509_COMMON_NAME
from golem.rpc import utils as rpc_utils

logger = logging.getLogger(__name__)


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

        if valid_ipv4(self.host) and IPAddress(self.host).is_loopback():
            # IPv4 loopback address replaced with hostname
            self.host = "localhost"

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

    # pylint: disable=too-many-arguments
    def __init__(self, address, mapping=None,
                 cert_manager=None, use_ipv6=False,
                 crsb_user=None, crsb_user_secret=None) -> None:
        self.address = address
        if mapping is None:
            mapping = {}
        self.mapping = mapping

        self.ready = Deferred()
        self.connected = False

        self._cert_manager = cert_manager

        self._client = None
        self._reconnect_service = None
        self._use_ipv6 = use_ipv6

        self.config = types.ComponentConfig(realm=address.realm)
        self.crsb_user = crsb_user
        self.crsb_user_secret = crsb_user_secret

        # pylint:disable=bad-super-call
        super(self.__class__, self).__init__(self.config)  # type: ignore

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

    def onConnect(self):
        if self.crsb_user and self.crsb_user_secret:
            logger.info("Client connected, starting WAMP-Ticket challenge.")
            logger.debug("crsb_user=%r, realm=%r, ",
                         self.crsb_user, self.config.realm)
            self.join(self.config.realm, ["wampcra"], self.crsb_user.name)
        else:
            logger.info("Attempting to log in as anonymous")

    def onChallenge(self, challenge):
        if challenge.method == "wampcra":
            logger.info(f"WAMP-Ticket challenge received.")
            logger.debug("challenge=%r", challenge)
            signature = auth.compute_wcs(self.crsb_user_secret.encode('utf8'),
                                         challenge.extra['challenge'].encode('utf8')) # noqa # pylint: disable=line-too-long
            return signature.decode('ascii')

        else:
            raise Exception("Invalid authmethod {}".format(challenge.method))

    @inlineCallbacks
    def onJoin(self, details):
        yield self.register_procedures(self.mapping)
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
    def add_procedures(self, mapping):
        self.mapping.update(mapping)
        yield self.register_procedures(mapping)

    @inlineCallbacks
    def register_procedures(self, mapping):
        for uri, procedure in mapping.items():
            deferred = self.register(procedure, uri)
            deferred.addErrback(self._on_error)
            yield deferred

    @rpc_utils.expose('sys.exposed_procedures')
    def exposed_procedures(self):
        exposed: typing.Dict[str, str] = {}
        for registration in self._registrations.values():
            fn = registration.endpoint.fn
            qname = '.'.join((fn.__module__, fn.__qualname__))
            exposed[registration.procedure] = qname
        return exposed

    def is_open(self):
        return self.connected and self.is_attached() and not self.is_closing()

    def is_closing(self):
        return self._goodbye_sent or self._transport_is_closing

    @staticmethod
    def _on_error(err):
        logger.error("RPC: Session error: %r", err)
        return err


class ClientProxy:  # pylint: disable=too-few-public-methods
    PREFIXES: typing.Tuple[str, ...] = (
        'golem.client.Client.',
        'golem.node.Node.',
    )

    def __init__(self, session: ApplicationSession) -> None:
        self._session: ApplicationSession = session
        self._mapping: typing.Dict[str, str] = {}  # attribute_name, wamp_uri

        if session is None:
            self._ready = Deferred()
            return
        txdeferred = self._call('sys.exposed_procedures')
        txdeferred.addCallback(self._init_mapping)
        txdeferred.addErrback(logger.error)
        self._ready = txdeferred

    def __getattr__(self, name):
        if name.startswith('_'):
            return super().__getattr__(name)  # pylint: disable=no-member
        if not self._ready.called:
            raise RuntimeError("Proxy not ready yet")
        try:
            wamp_uri = self._mapping[name]
        except KeyError:
            raise AttributeError("{name} not mapped".format(name=name))
        return functools.partial(self._call, wamp_uri)

    def _init_mapping(self, result):
        for wamp_uri, full_name in result.items():
            for prefix in self.PREFIXES:
                if not full_name.startswith(prefix):
                    continue
                short_name = full_name[len(prefix):]
                self._mapping[short_name] = wamp_uri

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
            logger.error("RPC: call error: %r", err)
            return err


class Publisher:  # pylint: disable=too-few-public-methods
    def __init__(self, session):
        self.session = session

    def publish(self, event_alias, *args, **kwargs) \
            -> typing.Optional[Deferred]:
        """
        :return: deferred autobahn.wamp.request.Publication on success or None
                 if session is closing or there's an error
        """
        if self.session.is_open():
            try:
                return self.session.publish(str(event_alias), *args,
                                            **kwargs)
            except WampError as e:
                logger.error("RPC: Cannot publish '%s', because %r",
                             event_alias, e)
        elif not self.session.is_closing():
            logger.warning("RPC: Cannot publish '%s', session is not yet "
                           "established", event_alias)
        return None
