import logging
import struct
import time

import golem_messages
from golem_messages import message
from twisted.internet.defer import maybeDeferred
from twisted.internet.endpoints import TCP4ServerEndpoint, \
    TCP4ClientEndpoint, TCP6ServerEndpoint, TCP6ClientEndpoint, \
    HostnameEndpoint
from twisted.internet.protocol import connectionDone

from golem.core.databuffer import DataBuffer
from golem.core.hostaddress import get_host_addresses
from golem.network.transport.limiter import CallRateLimiter
from .network import Network, SessionProtocol, IncomingProtocolFactoryWrapper, \
    OutgoingProtocolFactoryWrapper
from .spamprotector import SpamProtector

# Import helpers to this namespace
from .tcpnetwork_helpers import SocketAddress, TCPListenInfo  # noqa pylint: disable=unused-import
from .tcpnetwork_helpers import TCPListeningInfo, TCPConnectInfo  # noqa pylint: disable=unused-import

logger = logging.getLogger(__name__)

MAX_MESSAGE_SIZE = 2 * 1024 * 1024


###############
# TCP Network #
###############


class TCPNetwork(Network):

    def __init__(self, protocol_factory, use_ipv6=False, timeout=5,
                 limit_connection_rate=False):
        """
        TCP network information
        :param ProtocolFactory protocol_factory: Protocols should be at least
                                                 ServerProtocol implementation
        :param bool use_ipv6: *Default: False* should network use IPv6 server
                              endpoint?
        :param int timeout: *Default: 5*
        :return None:
        """
        from twisted.internet import reactor
        self.reactor = reactor
        self.incoming_protocol_factory = IncomingProtocolFactoryWrapper(
            protocol_factory)
        self.outgoing_protocol_factory = OutgoingProtocolFactoryWrapper(
            protocol_factory)
        self.use_ipv6 = use_ipv6
        self.timeout = timeout
        self.active_listeners = {}
        self.host_addresses = get_host_addresses()

        if limit_connection_rate:
            self.rate_limiter = CallRateLimiter()
        else:
            self.rate_limiter = None

    def connect(self, connect_info: TCPConnectInfo) -> None:
        """
        Connect network protocol factory to address from connect_info via TCP.
        """
        self.__try_to_connect_to_addresses(connect_info)

    def listen(self, listen_info: TCPListenInfo) -> None:
        """
        Listen with network protocol factory on a TCP socket
        specified by listen_info
        """
        self.__try_to_listen_on_port(listen_info)

    def stop_listening(self, listening_info):
        """
        Stop listening on a TCP socket specified by listening_info
        :param TCPListeningInfo listening_info:
        :param kwargs: any additional parameters
        :return None|Deferred:
        """
        port = listening_info.port
        listening_port = self.active_listeners.get(port)
        if listening_port:
            defer = maybeDeferred(listening_port.stopListening)

            if not defer.called:
                defer.addCallback(
                    TCPNetwork.__stop_listening_success,
                    listening_info.stopped_callback,
                )
                defer.addErrback(
                    TCPNetwork.__stop_listening_failure,
                    listening_info.stopped_errback,
                )
            del self.active_listeners[port]
            return defer
        else:
            logger.warning(
                "Can't stop listening on port %r, wasn't listening.",
                port,
            )
            TCPNetwork.__stop_listening_failure(
                None,
                listening_info.stopped_errback,
            )
            return None

    def __filter_host_addresses(self, addresses):
        result = []

        for sa in addresses:
            if sa.address in self.host_addresses\
                    and sa.port in self.active_listeners:
                logger.debug(
                    'Can\'t connect with self: %r:%r',
                    sa.address,
                    sa.port
                )
                continue
            result.append(sa)
        return result

    def __try_to_connect_to_addresses(self, connect_info: TCPConnectInfo):
        addresses = self.__filter_host_addresses(connect_info.socket_addresses)
        logger.debug('__try_to_connect_to_addresses(%r) filtered', addresses)

        if not addresses:
            logger.warning("No addresses for connection given")
            TCPNetwork.__call_failure_callback(connect_info.failure_callback)
            return

        if self.rate_limiter:
            self.rate_limiter.call(self.__try_to_connect_to_address,
                                   connect_info)
        else:
            self.__try_to_connect_to_address(connect_info)

    def __try_to_connect_to_address(self, connect_info: TCPConnectInfo):
        address = connect_info.socket_addresses[0].address
        port = connect_info.socket_addresses[0].port

        logger.debug("Connection to host %r: %r", address, port)

        use_ipv6 = connect_info.socket_addresses[0].ipv6
        use_hostname = connect_info.socket_addresses[0].hostname
        if use_ipv6:
            endpoint = TCP6ClientEndpoint(self.reactor, address, port,
                                          self.timeout)
        elif use_hostname:
            endpoint = HostnameEndpoint(self.reactor, address, port,
                                        self.timeout)
        else:
            endpoint = TCP4ClientEndpoint(self.reactor, address, port,
                                          self.timeout)

        defer = endpoint.connect(self.outgoing_protocol_factory)

        defer.addCallback(self.__connection_established,
                          self.__connection_to_address_established,
                          connect_info)
        defer.addErrback(self.__connection_failure,
                         self.__connection_to_address_failure,
                         connect_info)

    @staticmethod
    def __connection_established(conn, established_callback,
                                 connect_info: TCPConnectInfo):
        pp = conn.transport.getPeer()
        logger.debug("Connection established %r %r", pp.host, pp.port)
        TCPNetwork.__call_established_callback(
            established_callback,
            conn.session,
            connect_info,
        )

    @staticmethod
    def __connection_failure(err_desc, failure_callback,
                             connect_info: TCPConnectInfo):
        logger.debug("Connection failure. %r", err_desc)
        TCPNetwork.__call_failure_callback(failure_callback, connect_info)

    @staticmethod
    def __connection_to_address_established(conn,
                                            connect_info: TCPConnectInfo):
        TCPNetwork.__call_established_callback(
            connect_info.established_callback,
            conn,
        )

    def __connection_to_address_failure(self, connect_info: TCPConnectInfo):
        if len(connect_info.socket_addresses) > 1:
            connect_info.socket_addresses.pop(0)
            self.__try_to_connect_to_addresses(connect_info)
        else:
            TCPNetwork.__call_failure_callback(connect_info.failure_callback)

    def __try_to_listen_on_port(self, listen_info: TCPListenInfo):
        if self.use_ipv6:
            ep = TCP6ServerEndpoint(self.reactor, listen_info.port_start)
        else:
            ep = TCP4ServerEndpoint(self.reactor, listen_info.port_start)

        defer = ep.listen(self.incoming_protocol_factory)

        defer.addCallback(
            self.__listening_established,
            listen_info.established_callback,
        )
        defer.addErrback(
            self.__listening_failure,
            listen_info
        )

    def __listening_established(self, listening_port, established_callback):
        port = listening_port.getHost().port
        self.active_listeners[port] = listening_port
        TCPNetwork.__call_established_callback(
            established_callback,
            port,
        )

    def __listening_failure(self, err_desc, listen_info: TCPListenInfo):
        err = str(err_desc.value)
        logger.debug("Can't listen on port %r: %r", listen_info.port_start, err)
        if listen_info.port_start < listen_info.port_end:
            listen_info.port_start += 1
            self.__try_to_listen_on_port(listen_info)
        else:
            TCPNetwork.__call_failure_callback(listen_info.failure_callback)

    @staticmethod
    def __call_failure_callback(failure_callback, *args, **kwargs):
        if failure_callback is None:
            return
        failure_callback(*args, **kwargs)

    @staticmethod
    def __call_established_callback(established_callback, result, *args,
                                    **kwargs):
        if established_callback is None:
            return
        established_callback(result, *args, **kwargs)

    @staticmethod
    def __stop_listening_success(result, callback):
        if result:
            logger.info("Stop listening result %r", result)
        if callback is None:
            return
        callback()

    @staticmethod
    def __stop_listening_failure(fail, errback):
        logger.error("Can't stop listening %r", fail)
        TCPNetwork.__call_failure_callback(errback)

#############
# Protocols #
#############


class BasicProtocol(SessionProtocol):

    """Connection-oriented basic protocol for twisted, supports message
       serialization
    """

    def __init__(self):
        super().__init__()
        self.opened = False
        self.db = DataBuffer()
        self.spam_protector = SpamProtector()

    def send_message(self, msg):
        """
        Serialize and send message
        :param Message msg: message to send
        :return bool: return True if message has been send, False otherwise
        """
        if not self.opened:
            logger.warning("Send message %s failed - connection closed", msg)
            return False

        try:
            msg_to_send = self._prepare_msg_to_send(msg)
        except golem_messages.exceptions.SerializationError:
            logger.exception('Cannot serialize message: %s', msg)
            raise

        if msg_to_send is None:
            return False

        self.transport.getHandle()
        self.transport.write(msg_to_send)

        return True

    def close(self):
        """
        Close connection, after writing all pending
        (flush the write buffer and wait for producer to finish).
        :return None:
        """
        self.transport.loseConnection()

    def close_now(self):
        """
        Close connection ASAP, doesn't flush the write buffer or wait for
        the producer to finish
        :return:
        """
        self.opened = False
        self.transport.abortConnection()

    # Protocol functions
    def connectionMade(self):
        """Called when new connection is successfully opened"""
        SessionProtocol.connectionMade(self)
        self.opened = True

    def dataReceived(self, data):
        """Called when additional chunk of data
            is received from another peer"""
        if not self._can_receive():
            return

        if not self.session:
            logger.warning("No session argument in connection state")
            return

        self._interpret(data)

    def connectionLost(self, reason=connectionDone):
        """Called when connection is lost (for whatever reason)"""
        self.opened = False
        if self.session:
            self.session.dropped()

        SessionProtocol.connectionLost(self, reason)

    # Protected functions
    def _prepare_msg_to_send(self, msg):
        ser_msg = golem_messages.dump(msg, None, None)

        db = DataBuffer()
        db.append_len_prefixed_bytes(ser_msg)
        return db.read_all()

    def _can_receive(self) -> bool:
        return self.opened and isinstance(self.db, DataBuffer)

    def _interpret(self, data):
        self.session.last_message_time = time.time()
        self.db.append_bytes(data)
        mess = self._data_to_messages()
        for m in mess:
            self.session.interpret(m)

    def _load_message(self, data):
        msg = golem_messages.load(data, None, None)
        logger.debug(
            'BasicProtocol._load_message(): received %r',
            msg,
        )
        return msg

    def _data_to_messages(self):
        messages = []

        for data in self.db.get_len_prefixed_bytes():
            if len(data) > MAX_MESSAGE_SIZE:
                logger.info(
                    'Ignoring huge message %dB from %r',
                    len(data),
                    self.transport.getPeer(),
                )
                continue

            try:
                if not self.spam_protector.check_msg(data):
                    continue
                msg = self._load_message(data)
            except golem_messages.exceptions.HeaderError as e:
                logger.debug(
                    "Invalid message header: %s from %s. Ignoring.",
                    e,
                    self.transport.getPeer(),
                )
                continue
            except golem_messages.exceptions.VersionMismatchError as e:
                logger.debug(
                    "Message version mismatch: %s from %s. Closing.",
                    e,
                    self.transport.getPeer(),
                )
                msg = message.base.Disconnect(
                    reason=message.base.Disconnect.REASON.ProtocolVersion,
                )
                self.send_message(msg)
                self.close()
                return []
            except golem_messages.exceptions.MessageError as e:
                logger.info("Failed to deserialize message (%r) %r", e, data)
                logger.debug(
                    "BasicProtocol._data_to_messages() failed %r",
                    data,
                    exc_info=True,
                )
                continue

            messages.append(msg)

        return messages


class ServerProtocol(BasicProtocol):
    """ Basic protocol connected to server instance
    """

    def __init__(self, server):
        """
        :param Server server: server instance
        :return None:
        """
        BasicProtocol.__init__(self)
        self.server = server

    # Protocol functions
    def connectionMade(self):
        """Called when new connection is successfully opened"""
        BasicProtocol.connectionMade(self)
        self.server.new_connection(self.session)

    def _can_receive(self) -> bool:
        if not self.opened:
            logger.warning("Protocol is closed")
            return False

        if not self.session and self.server:
            self.opened = False
            logger.warning('Peer for connection is None')
            return False

        return True


class SafeProtocol(ServerProtocol):
    """More advanced version of server protocol, support for serialization,
       encryption, decryption and signing messages
    """

    def _prepare_msg_to_send(self, msg):
        logger.debug('SafeProtocol._prepare_msg_to_send(%r)', msg)
        if self.session is None:
            logger.error("Wrong session, not sending message")
            return None

        logger.debug(
            'Sending: %r, using session: %r', msg.__class__, self.session)
        serialized = golem_messages.dump(
            msg,
            self.session.my_private_key,
            self.session.theirs_public_key,
        )
        length = struct.pack("!L", len(serialized))
        return length + serialized

    def _load_message(self, data):
        msg = golem_messages.load(
            data,
            self.session.my_private_key,
            self.session.theirs_public_key,
        )
        logger.debug(
            'SafeProtocol._load_message(): received %r',
            msg,
        )
        return msg
