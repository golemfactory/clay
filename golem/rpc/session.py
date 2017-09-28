import logging
from asyncio import Future

from autobahn.asyncio import ApplicationSession
from autobahn.asyncio.wamp import ApplicationRunner
from autobahn.asyncio.websocket import WampWebSocketClientFactory
from autobahn.wamp import ProtocolError
from autobahn.wamp import types

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
        self.address = '{}://{}:{}'.format(self.protocol,
                                           self.host, self.port)

    def __str__(self):
        return str(self.address)

    def __unicode__(self):
        return self.address


class WebSocketAddress(RPCAddress):

    def __init__(self, host, port, realm, ssl=False):
        self.realm = str(realm)
        self.ssl = ssl

        protocol = 'wss' if ssl else 'ws'
        super(WebSocketAddress, self).__init__(protocol, host, port)


class Session(ApplicationSession):

    def __init__(self, address, methods=None, events=None):
        self.address = address
        self.methods = methods or []
        self.events = events or []
        self.subs = {}

        self.ready = Future()
        self.connected = False

        self.config = types.ComponentConfig(realm=address.realm)
        super(Session, self).__init__(self.config)

    def connect(self, ssl=None, proxy=None, headers=None, auto_reconnect=True,
                log_level='info'):

        runner = ApplicationRunner(
            url=str(self.address),
            realm=self.address.realm,
            ssl=ssl,
            proxy=proxy,
            headers=headers
        )

        future = runner.run(make=self, start_loop=True)

        def done(f):
            try:
                self.ready.set_result(f.result())
            except Exception as exc:
                self.ready.set_exception(exc)

        future.add_done_callback(done)
        return self.ready

    async def onJoin(self, details):
        await self.register_methods(self.methods)
        await self.register_events(self.events)
        self.connected = True
        if not self.ready.done():
            self.ready.set_result(details)

    def onLeave(self, details):
        self.connected = False
        if not self.ready.done():
            self.ready.set_exception(Exception(details or "Unknown error"))
        super(Session, self).onLeave(details)

    def onDisconnect(self):
        self.connected = False
        super(Session, self).onDisconnect()

    async def register_methods(self, methods):
        for method, rpc_name in methods:
            await self.register(method, str(rpc_name))

    async def register_events(self, events):
        for method, rpc_name in events:
            await self.subscribe(method, str(rpc_name))

    async def unregister_events(self, event_names):
        for event_name in event_names:
            if event_name in self.subs:
                await self.subs[event_name].unsubscribe()
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
            future = self._session.call(str(method_alias), *args, **kwargs)
            future.add_done_callback(self._on_error)
        else:
            future = Future()
            if not self._session.is_closing():
                future.set_exception(ProtocolError("RPC: session is not "
                                                   "yet established"))
        return future

    def _on_error(self, err):
        if isinstance(err, Exception) and not self._session.is_closing():
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
