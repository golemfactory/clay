import logging
import threading
import time
from typing import Dict, Tuple, Any, List, Type, Callable

from eth_utils import encode_hex
from twisted.internet.defer import inlineCallbacks

from golem.core.net import events, NetworkService, NetworkServiceError
from golem.core.net.message import LabeledMessage
from golem.core.net.transport import ProxyTransport
from golem.network.transport.limiter import CallRateLimiter
from golem.network.transport.network import Network
from golem.network.transport.tcpnetwork_helpers import TCPConnectInfo, \
    SocketAddress, TCPListenInfo, TCPListeningInfo

logger = logging.getLogger(__name__)


LISTEN_TIMEOUT: int = 2
CONNECT_TIMEOUT: int = 3


class EventLoop:
    def __init__(
        self,
        network: NetworkService,
        handler: Callable,
    ) -> None:
        self._network = network
        self._handler = handler

        self._stop = threading.Event()
        self._thread = threading.Thread(
            name="core.net:events",
            daemon=True,
            target=self._run
        )

    @property
    def running(self) -> bool:
        return not self._stop.is_set() and self._thread.is_alive()

    def start(self) -> None:
        if not self.running:
            self._thread.start()

    def stop(self) -> None:
        if self.running:
            self._stop.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            self._loop()

    def _loop(self):
        try:
            args = self._network.poll(1)
        except NetworkServiceError as exc:
            logger.error('Network poll error: %r', exc)
            return

        if not args:
            time.sleep(0.25)
            return

        try:
            event = events.Event.convert_from(args)
            self._handler(event)
        except (ValueError, AttributeError, IndexError) as exc:
            logger.error("Invalid event %r: %r", args, exc)


class ProxyNetwork(Network):

    class _Connections:
        def __init__(self):
            # (ip, port): connection info
            self.pending: Dict[Tuple[str, int], TCPConnectInfo] = dict()
            # (ip, port): { protocol_id: connection }
            self.established: Dict[Tuple[str, int], Dict[str, Any]] = dict()

    def __init__(
        self,
        priv_key: bytes,
        use_ipv6: bool = False
    ) -> None:

        from twisted.internet import reactor
        self._reactor = reactor

        self._address = ('::0' if use_ipv6 else '0.0.0.0', None)
        self._priv_key = priv_key

        self._network = NetworkService()
        self._event_loop = EventLoop(self._network, self._handle)
        self._rate_limiter = CallRateLimiter()
        self._conns = self._Connections()

        self._listen_lock = None
        self._in_factories = None
        self._out_factories = None

    def start(self, in_factories, out_factories):
        assert in_factories, "Incoming connection factories are required"
        assert out_factories, "Outgoing connection factories are required"

        self._in_factories = in_factories
        self._out_factories = out_factories
        self._event_loop.start()

    # Network interface

    def listen(self, listen_info: TCPListenInfo) -> None:
        self._listen(listen_info)

    def stop_listening(self, listening_info: TCPListeningInfo):
        self._network.stop()
        self._event_loop.stop()

    def connect(self, connect_info: TCPConnectInfo) -> None:
        addresses = self._filter_host_addresses(connect_info.socket_addresses)
        logger.debug('connect(%r) filtered', addresses)

        if addresses:
            self._rate_limiter.call(
                self._reactor.callLater, 0,
                self._connect, connect_info
            )
        else:
            connect_info.failure_callback()

    def disconnect(self, peer_id: str):
        try:
            if not self._network.disconnect(peer_id):
                raise NetworkServiceError(
                    'Cannot disconnect from %s: network is not running',
                    peer_id
                )
        except NetworkServiceError as exc:
            logger.warning('Network: %r', exc)

    def send(self, peer_id: str, protocol_id: int, blob: bytes):
        msg = LabeledMessage(protocol_id, blob).pack()
        if not self._network.send(peer_id, msg):
            logger.error("Couldn't send a message to %s", peer_id)

    @inlineCallbacks
    def _connect(self, connect_info: TCPConnectInfo) -> None:
        address = yield self._resolve_address(connect_info.socket_addresses[0])

        if address in self._conns.established:
            # connections = self._conns.established[address]
            # connection = connections[connect_info.protocol_id]
            # connect_info.established_callback(connection.session)
            logger.info('Already connected to %s:%r', *address)
            return

        if address in self._conns.pending:
            logger.info('Already connecting to %s:%r', *address)
            return

        logger.info("Connecting to %s:%r", *address)

        try:
            if not self._network.connect(*address):
                raise NetworkServiceError(f'Unable to connect to {address}: '
                                          'server is not running')
        except Exception:  # pylint: disable=broad-except
            if connect_info.socket_addresses:
                connect_info.socket_addresses.pop(0)
                self._connect(connect_info)
            else:
                connect_info.failure_callback()
        else:
            self._conns.pending[address] = connect_info
            self._reactor.callLater(CONNECT_TIMEOUT, self._connect_error,
                                    address)

    def _connect_error(self, address: Tuple[str, int]):
        connect_info = self._conns.pending.pop(address, None)
        if connect_info:
            connect_info.failure_callback()

    def _listen(self, listen_info: TCPListenInfo):
        address = self._address[0], listen_info.port_start

        if self._listen_lock:
            return logger.info('Already trying to listen on %s:%r', *address)

        try:
            if not self._network.start(self._priv_key, *address):
                raise NetworkServiceError(f'Unable to listen on {address}')
        except NetworkServiceError as exc:
            if listen_info.port_start < listen_info.port_end:
                listen_info.port_start += 1
                self._listen(listen_info)
            else:
                listen_info.failure_callback(f'Network error: {exc}')
        else:
            self._listen_lock = listen_info
            self._reactor.callLater(LISTEN_TIMEOUT, self._listen_error,
                                    'Timeout')

    def _listen_error(self, message: str) -> None:
        if not self._listen_lock:
            return

        listen_info, self._listen_lock = self._listen_lock, None
        listen_info.failure_callback(message, listen_info)

    def _filter_host_addresses(self, addresses) -> List[SocketAddress]:
        return list(filter(self._filter_host_address, addresses))

    def _filter_host_address(self, address: SocketAddress) -> bool:
        as_tuple = (address.address, address.port)
        return (
            as_tuple not in self._conns.established and
            as_tuple != self._address
        )

    @inlineCallbacks
    def _resolve_address(self, socket_address: SocketAddress) -> str:
        if socket_address.hostname:
            host = yield self._reactor.resolve(socket_address.address)
        else:
            host = socket_address.address
        return host, socket_address.port

    # Event handlers

    def _handle(self, event: events.Event) -> None:
        if not event:
            return

        handler = self.EVENT_HANDLERS.get(event.__class__)
        if handler:
            self._reactor.callFromThread(handler, self, event)
        else:
            logger.error("Unknown event: %r", event)

    def _handle_started(self, event: events.Listening) -> None:
        if not self._listen_lock:
            return

        self._address = event.address
        logger.info('Network listening on %s:%r', *self._address)

        listen_info, self._listen_lock = self._listen_lock, None
        listen_info.established_callback(SocketAddress(*event.address))

    def _handle_stopped(self, _event: events.Terminated) -> None:
        if self._listen_lock:
            return

        logger.info("Network stopped")

        for key, conns in dict(self._conns.established).items():
            for conn in conns.values():
                conn.session.dropped()
            self._conns.established.pop(key, None)

    def _handle_connected(self, event: events.Connected) -> None:
        connect_info = self._conns.pending.pop(event.endpoint.address, None)
        address = event.endpoint.address
        key_id = encode_hex(event.peer_pubkey)[2:]

        def create_conn(factory):
            t = ProxyTransport(network=self,
                               address=address,
                               protocol_id=factory.protocol_id,
                               peer_id=event.peer_id)
            c = factory.buildProtocol(address)
            c.makeConnection(t)
            return c

        if connect_info:
            connections = {f.protocol_id: create_conn(f)
                           for f in self._out_factories}
            self._conns.established[address] = connections

            if connect_info.protocol_id in connections:
                connection = connections[connect_info.protocol_id]
                connection.session.key_id = key_id
                connect_info.established_callback(connection.session)
            else:
                logger.warning('_handle_connected: Unknown protocol id: %r',
                               connect_info.protocol_id)

        else:
            self._conns.established[address] = {
                f.protocol_id: create_conn(f) for f in self._in_factories
            }

    def _handle_disconnected(self, event: events.Disconnected) -> None:
        conns = self._conns.established.pop(event.endpoint.address, None)
        if not conns:
            return

        for conn in conns.values():
            conn.session.dropped()

        logger.info("%s disconnected from %r", *event.endpoint.address)

    def _handle_message(self, event: events.Message) -> None:
        address = event.endpoint.address
        msg = LabeledMessage.unpack(event.blob)

        conns = self._conns.established.get(address)
        conn = conns.get(msg.label) if conns else None

        if conn:
            conn.dataReceived(msg.data)
        else:
            logger.warning('_handle_message: No session for peer: %s',
                           event.peer_id)

    @staticmethod
    def _handle_clogged(event: events.Clogged) -> None:
        logger.warning('Peer clogged:', event.peer_id)

    @staticmethod
    def _handle_error(event: events.Error) -> None:
        logger.error('Error:', event.error)

    EVENT_HANDLERS: Dict[Type[events.Event], Callable] = {
        events.Listening: _handle_started,
        events.Terminated: _handle_stopped,
        events.Connected: _handle_connected,
        events.Disconnected: _handle_disconnected,
        events.Message: _handle_message,
        events.Clogged: _handle_clogged,
        events.Error: _handle_error,
    }
