import logging
from abc import ABCMeta
from collections import namedtuple

from queue import Empty, Queue
from threading import Event, Thread
from typing import Callable, Dict, Type, Tuple, List, Any

from twisted.internet.defer import inlineCallbacks

from golem_core import CoreNetwork, CoreError
from golem_core.enums import TransportProtocol, ErrorKind
from golem_core.events import *

from golem.core.hostaddress import get_host_addresses
from golem.network.transport.limiter import CallRateLimiter
from golem.network.transport.network import Network
from golem.network.transport.tcpnetwork_helpers import TCPListeningInfo, \
    TCPListenInfo, TCPConnectInfo, SocketAddress

logger = logging.getLogger(__name__)


LISTEN_TIMEOUT = 2
CONNECT_TIMEOUT = 3


class NativeModuleTransport:

    Host = namedtuple('Host', ['host', 'port'])

    def __init__(self, network, protocol_id, peer, host):
        self.network = network
        self.protocol_id = protocol_id
        self.peer = self.Host(peer[0], peer[1])
        self.host = self.Host(host[0], host[1])
        self._disconnecting = False

    def getPeer(self):  # noqa
        return self.peer

    def getHost(self):  # noqa
        return self.host

    @staticmethod
    def getHandle():  # noqa
        pass

    def loseConnection(self):  # noqa
        if self._disconnecting:
            return
        self._disconnecting = True
        self.network.disconnect(self.peer.host, self.peer.port)

    def abortConnection(self):  # noqa
        self.loseConnection()

    def write(self, data: bytes) -> None:
        self.network.send(
            self.peer[0], self.peer[1],
            self.protocol_id, data
        )


class NativeEventQueue(metaclass=ABCMeta):

    def __init__(self, queue: Queue, handler: Callable) -> None:

        self._queue = queue
        self._handler = handler

        self._stop = Event()
        self._thread = Thread(
            daemon=True,
            target=self._run
        )

    @property
    def running(self) -> bool:
        return self._thread.is_alive()

    def start(self) -> None:
        if not self.running:
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            self._loop()
        self.stop()

    def _loop(self):
        try:
            args = self._queue.get(block=True, timeout=1)
        except Empty:
            return

        try:
            event = CoreEvent.convert_from(args)
        except (ValueError, AttributeError, IndexError) as exc:
            logger.error("Invalid event %r: %r", args, exc)
        else:
            self._handler(event)


class NativeNetwork(Network):

    def __init__(
        self,
        use_ipv6: bool = False
    ) -> None:

        self._in_factories = None
        self._out_factories = None

        self._address = ('::0' if use_ipv6 else '0.0.0.0', None)
        self._host_addresses = get_host_addresses()

        self._conns: Dict[Tuple[str, int], Dict[int, Any]] = dict()
        self._pending_conns: Dict[Tuple[str, int], TCPConnectInfo] = dict()
        self._pending_listen = None

        self._rate_limiter = CallRateLimiter()
        self._reactor = self._get_reactor()

        self._queue = Queue()
        self._network = CoreNetwork(self._queue)
        self._events = NativeEventQueue(self._queue, self._handle)

    def start(self, in_factories, out_factories):
        self._in_factories = in_factories
        self._out_factories = out_factories

        self._events.start()

    # Network interface

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

    def disconnect(self, address: str, port: int):
        tcp_id = TransportProtocol.Tcp.value

        try:
            if not self._network.disconnect(tcp_id, address, port):
                raise CoreError('Cannot disconnec from %s:%r: network is not'
                                'running', *address)
        except CoreError as exc:
            logger.warning('Network: %r', exc)

    def listen(self, listen_info: TCPListenInfo) -> None:
        self._listen(listen_info)

    def stop_listening(self, listening_info: TCPListeningInfo):
        try:
            self._network.stop()
        except CoreError as exc:
            if ErrorKind.from_core_error(exc) is ErrorKind.Mailbox:
                logger.debug('Already stopping the network')
            else:
                raise

    def send(self, address: str, port: int, protocol_id: int, data: bytes):
        sent = self._network.send(
            TransportProtocol.Tcp.value,
            address, port,
            protocol_id, data
        )

        if not sent:
            logger.error("Couldn't send a message to %s:%r", *address)

    @inlineCallbacks
    def _connect(self, connect_info: TCPConnectInfo) -> None:
        address = yield self._resolve_address(connect_info.socket_addresses[0])

        if address in self._conns:
            connection = self._conns[address][connect_info.protocol_id]
            connect_info.established_callback(connection.session)
            return logger.info('Already connected to %s:%r', *address)

        if address in self._pending_conns:
            return logger.info('Already connecting to %s:%r', *address)

        logger.info("Connecting to %s:%r", *address)

        try:
            if not self._network.connect(TransportProtocol.Tcp.value,
                                         *address):
                raise CoreError(f'Unable to connect to {address}: server '
                                'is not running')
        except CoreError:
            if connect_info.socket_addresses:
                connect_info.socket_addresses.pop(0)
                self._connect(connect_info)
            else:
                connect_info.failure_callback()
        else:
            self._pending_conns[address] = connect_info
            self._reactor.callLater(CONNECT_TIMEOUT, self._connect_error,
                                    address)

    def _connect_error(self, socket_address: Tuple[str, int]):
        connect_info = self._pending_conns.pop(socket_address, None)
        if connect_info:
            connect_info.failure_callback()

    def _listen(self, listen_info: TCPListenInfo):
        address = self._address[0], listen_info.port_start

        if self._pending_listen:
            return logger.info('Already trying to listen on %s:%r', *address)

        try:
            if not self._network.run(*address):
                raise CoreError(f'Unable to listen on {address}')
        except CoreError as exc:
            if listen_info.port_start < listen_info.port_end:
                listen_info.port_start += 1
                self._listen(listen_info)
            else:
                listen_info.failure_callback(f'Network error: {exc}')
        else:
            self._pending_listen = listen_info
            self._reactor.callLater(LISTEN_TIMEOUT, self._listen_error,
                                    'Timeout')

    def _listen_error(self, message: str) -> None:
        if not self._pending_listen:
            return

        listen_info = self._pending_listen
        self._pending_listen = None
        listen_info.failure_callback(message, listen_info)

    def _filter_host_addresses(self, addresses) -> List[SocketAddress]:
        return list(filter(self._filter_host_address, addresses))

    def _filter_host_address(self, address: SocketAddress) -> bool:
        as_tuple = (address.address, address.port)
        return as_tuple not in self._conns and as_tuple != self._address

    @inlineCallbacks
    def _resolve_address(self, socket_address: SocketAddress) -> str:
        if socket_address.hostname:
            host = yield self._reactor.resolve(socket_address.address)
        else:
            host = socket_address.address
        return host, socket_address.port

    @staticmethod
    def _get_reactor():
        from twisted.internet import reactor
        return reactor

    # Event handlers

    def _handle(self, event: BaseEvent) -> None:
        handler = self.EVENT_HANDLERS.get(event.__class__)
        if handler:
            self._reactor.callFromThread(handler, self, event)
        else:
            logger.error("Unhandled event: %r", event)

    def _handle_exiting(self, _: Exiting) -> None:
        self._events.stop()

    def _handle_started(self, event: Started) -> None:
        self._address = event.address
        if not self._pending_listen:
            return

        logger.info('Network started')

        listen_info = self._pending_listen
        self._pending_listen = None
        listen_info.established_callback(SocketAddress(*event.address))

    def _handle_stopped(self, event: Stopped) -> None:
        logger.info("%r has stopped", event.transport_protocol.name)

        for key, conns in list(self._conns.items()):
            for conn in conns.values():
                conn.session.dropped()
            self._conns[key] = dict()

    def _handle_connected(self, event: Connected) -> None:
        connect_info = self._pending_conns.pop(event.address, None)

        def create_conn(factory):
            t = NativeModuleTransport(network=self,
                                      protocol_id=factory.protocol_id,
                                      host=self._address,
                                      peer=event.address)
            c = factory.buildProtocol(event.address)
            c.makeConnection(t)
            return c

        if event.initiator and connect_info:
            self._conns[event.address] = {f.protocol_id: create_conn(f)
                                          for f in self._out_factories}

            connection = self._conns[event.address][connect_info.protocol_id]
            connect_info.established_callback(connection.session)

        elif not event.initiator:
            self._conns[event.address] = {f.protocol_id: create_conn(f)
                                          for f in self._in_factories}

        else:
            logger.warning('Unknown pending connection: %s:%r', *event.address)

    def _handle_disconnected(self, event: Disconnected) -> None:
        conns = self._conns.pop(event.address, None)
        if not conns:
            return

        for conn in conns.values():
            conn.session.dropped()

        logger.info("%s disconnected from %s:%r", event.transport_protocol.name,
                    *event.address)

    def _handle_message(self, event: Message) -> None:
        conns = self._conns.get(event.address)
        if conns and event.encapsulated.protocol_id in conns:
            conn = conns[event.encapsulated.protocol_id]
            conn.dataReceived(event.encapsulated.message)
        else:
            logger.warning('Unknown session: %s:%r', *event.address)

    def _handle_log(self, event: Log) -> None:
        logger.log(event.log_level.value, event.message)

    EVENT_HANDLERS: Dict[Type[BaseEvent], Callable] = {
        Exiting: _handle_exiting,
        Started: _handle_started,
        Stopped: _handle_stopped,
        Connected: _handle_connected,
        Disconnected: _handle_disconnected,
        Message: _handle_message,
        Log: _handle_log,
    }
