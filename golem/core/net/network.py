import logging
import threading
import time
from typing import Dict, Tuple, List, Type, Callable, Optional, Iterable

from eth_utils import encode_hex
from twisted.internet.defer import inlineCallbacks
from twisted.internet.protocol import Protocol

from golem.core.net import events, NetworkService, NetworkServiceError
from golem.core.net.message import LabeledMessage
from golem.core.net.transport import LibP2PTransport
from golem.network.transport.limiter import CallRateLimiter
from golem.network.transport.network import Network, ProtocolFactory
from golem.network.transport.tcpnetwork_helpers import TCPConnectInfo, \
    SocketAddress, TCPListenInfo, TCPListeningInfo

logger = logging.getLogger(__name__)


LISTEN_TIMEOUT: int = 2  # s
CONNECT_TIMEOUT: int = 20  # s

AddressTuple = Tuple[str, int]


class TCPConnectInfoWrapper:
    """ Stores the connection state to the multiple addresses
        provided in TCPConnectInfo
    """

    def __init__(self, connect_info: TCPConnectInfo) -> None:
        self._inner = connect_info
        self._addresses = list(connect_info.socket_addresses)
        self._attempts = 0
        self._failures = 0

    #################
    # Proxy methods #
    #################

    @property
    def channel_id(self) -> int:
        return self._inner.channel_id

    def established_callback(self, *args, **kwargs):
        return self._inner.established_callback(*args, **kwargs)

    def failure_callback(self, *args, **kwargs):
        return self._inner.failure_callback(*args, **kwargs)

    #################
    # Class methods #
    #################

    @property
    def addresses(self) -> List[SocketAddress]:
        """ Returns a list of addresses provided in TCPConnectInfo """
        return list(self._inner.socket_addresses)

    def take_address(self) -> Optional[SocketAddress]:
        if not self._addresses:
            return None
        self._attempts += 1
        return self._addresses.pop(0)

    def address_failure(self):
        self._failures += 1

    def is_failure(self) -> bool:
        total = len(self._inner.socket_addresses)
        return self._attempts == self._failures == total > 0

    def finished(self) -> bool:
        return bool(self._addresses)


class LibP2PEventLoop:
    def __init__(
        self,
        network: NetworkService,
        handler: Callable,
    ) -> None:
        self._network = network
        self._handler = handler

        self._stop = threading.Event()
        self._thread = threading.Thread(
            name="core.net.event_loop",
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
            try:
                event_data = self._network.poll(1)
            except NetworkServiceError as exc:
                logger.error('Network poll error: %r', exc)
                continue

            if not event_data:
                time.sleep(0.25)
                continue

            try:
                event = events.Event.convert_from(event_data)
                self._handler(event)
            except (ValueError, AttributeError, IndexError) as exc:
                logger.error("Invalid event %r: %r", event_data, exc)


class LibP2PNetwork(Network):

    def __init__(
        self,
        priv_key: bytes,
        use_ipv6: bool = False,
    ) -> None:

        from twisted.internet import reactor
        self._reactor = reactor

        self._address = ('::0' if use_ipv6 else '0.0.0.0', None)
        self._priv_key = priv_key

        self._network = NetworkService()
        self._event_loop = LibP2PEventLoop(self._network, self._handle_event)
        self._rate_limiter = CallRateLimiter()

        # (ip, port): connection_info
        self._outgoing: Dict[AddressTuple, TCPConnectInfoWrapper] = dict()
        # (ip, port): { protocol_id: connection }
        self._connections: Dict[AddressTuple, Dict[int, Protocol]] = dict()

        self._in_factories = None
        self._out_factories = None
        self._listen_info = None

    def start(self, in_factories, out_factories):
        assert in_factories, "Incoming connection factories are required"
        assert out_factories, "Outgoing connection factories are required"

        self._in_factories = in_factories
        self._out_factories = out_factories
        self._event_loop.start()

    #####################
    # Network interface #
    #####################

    def listen(self, listen_info: TCPListenInfo) -> None:
        address = self._address[0], listen_info.port_start

        if self._listen_info:
            return logger.info('Already trying to listen on %s:%r',
                               self._address[0], self._listen_info.port_start)

        try:
            if not self._network.start(self._priv_key, *address):
                raise NetworkServiceError(f'Unable to listen on {address}')
        except NetworkServiceError as exc:
            if listen_info.port_start < listen_info.port_end:
                listen_info.port_start += 1
                self.listen(listen_info)
            else:
                listen_info.failure_callback(f'Network error: {exc}')
        else:
            self._priv_key = None
            self._listen_info = listen_info
            self._reactor.callLater(LISTEN_TIMEOUT, self._listen_error,
                                    'Timeout')

    def stop_listening(self, listening_info: TCPListeningInfo):
        if self._network:
            self._network.stop()

    def connect(self, connect_info: TCPConnectInfo) -> None:
        addresses = self._filter_host_addresses(connect_info.socket_addresses)
        logger.debug('connect(%r) filtered', addresses)

        if addresses:
            self._rate_limiter.call(
                self._reactor.callLater, 0,
                self._connect, TCPConnectInfoWrapper(connect_info)
            )
        else:
            connect_info.failure_callback()

    ###################
    # Class interface #
    ###################

    def disconnect(self, peer_id: str) -> None:
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
            logger.error("Cannot send a message to %s", peer_id)

    @inlineCallbacks
    def _connect(self, connect_info: TCPConnectInfoWrapper) -> None:
        address = yield self._resolve_address(connect_info.take_address())

        if address in self._connections:
            logger.info('Already connected to %s:%r', *address)
            connection = self._connections[address][connect_info.channel_id]
            connect_info.established_callback(connection.session)
            return

        if address in self._outgoing:
            logger.info('Already connecting to %s:%r', *address)
            return

        logger.info("Connecting to %s:%r", *address)

        if self._network.connect(*address):
            self._outgoing[address] = connect_info
            self._reactor.callLater(
                CONNECT_TIMEOUT,
                lambda: (
                    connect_info.address_failure(),
                    self._connect_error(connect_info, address)
                )
            )
        else:
            connect_info.address_failure()
            if connect_info.finished():
                self._connect_error(connect_info, address)
            else:
                self._connect(connect_info)

    @staticmethod
    def _connect_error(
        connect_info: TCPConnectInfoWrapper,
        address: AddressTuple,
    ) -> None:
        logger.debug('Unable to connect to %s:%r', *address)

        if connect_info.is_failure():
            logger.warning('Unable to connect to %r', connect_info.addresses)
            connect_info.failure_callback()

    def _listen_error(self, message: str) -> None:
        if not self._listen_info:
            return

        logger.error('Unable to listen on %r: %s', self._listen_info, message)

        listen_info, self._listen_info = self._listen_info, None
        listen_info.failure_callback(message, listen_info)

    def _filter_host_addresses(
        self,
        addresses: Iterable[SocketAddress],
    ) -> List[SocketAddress]:
        return list(filter(self._filter_host_address, addresses))

    def _filter_host_address(self, address: SocketAddress) -> bool:
        as_tuple = (address.address, address.port)
        return (
            as_tuple not in self._connections and
            as_tuple != self._address
        )

    @inlineCallbacks
    def _resolve_address(self, socket_address: SocketAddress) -> str:
        if socket_address.hostname:
            host = yield self._reactor.resolve(socket_address.address)
        else:
            host = socket_address.address
        return host, socket_address.port

    ##################
    # Event handlers #
    ##################

    def _handle_event(self, event: events.Event) -> None:
        if not event:
            return
        handler = self.EVENT_HANDLERS.get(event.__class__)
        if handler:
            self._reactor.callFromThread(handler, self, event)
        else:
            logger.error("Unknown event: %r", event)

    def _handle_started(self, event: events.Listening) -> None:
        if not self._listen_info:
            return

        self._address = event.address
        listen_info, self._listen_info = self._listen_info, None

        logger.info('Listening on %s:%r', *self._address)
        listen_info.established_callback(SocketAddress(*event.address))

    def _handle_stopped(self, _event: events.Terminated) -> None:
        if self._listen_info:
            return

        logger.info("Stopped")

        for key, conns in dict(self._connections).items():
            for conn in conns.values():
                conn.session.dropped()
            self._connections.pop(key, None)

        if self._event_loop:
            self._event_loop.stop()

    def _handle_connected(self, event: events.Connected) -> None:
        address = event.endpoint.address
        connect_info = self._outgoing.pop(address, None)

        if connect_info:
            factories = self._out_factories
        else:
            factories = self._in_factories

        self._connections[address] = {
            factory.channel_id: self.__create_protocol(factory, event, address)
            for factory in factories
        }

        if connect_info:
            if connect_info.channel_id not in self._connections[address]:
                raise ValueError("Invalid channel id")
            connection = self._connections[address][connect_info.channel_id]
            connect_info.established_callback(connection.session)

    def __create_protocol(
        self,
        factory: ProtocolFactory,
        event: events.Connected,
        address: AddressTuple,
    ) -> Protocol:
        conn = factory.buildProtocol(address)
        conn.makeConnection(LibP2PTransport(network=self,
                                            address=address,
                                            channel_id=factory.channel_id,
                                            peer_id=event.peer_id))
        conn.session.key_id = encode_hex(event.peer_pubkey)[2:]
        return conn

    def _handle_disconnected(self, event: events.Disconnected) -> None:
        conns = self._connections.pop(event.endpoint.address, None)
        if not conns:
            return

        for conn in conns.values():
            conn.session.dropped()

        logger.info("%s disconnected from %r (%s)", *event.endpoint.address,
                    event.peer_id)

    def _handle_message(self, event: events.Message) -> None:
        address = event.endpoint.address
        msg = LabeledMessage.unpack(event.blob)

        conns = self._connections.get(address)
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
