import logging
import struct
import time
from ipaddress import ip_address

import golem_messages
from golem_messages import message
from twisted.internet.defer import maybeDeferred
from twisted.internet.endpoints import TCP4ServerEndpoint, \
    TCP4ClientEndpoint, TCP6ServerEndpoint, TCP6ClientEndpoint
from twisted.internet.error import ConnectionDone

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

    def connect(self, connect_info, **kwargs):
        """
        Connect network protocol factory to address from connect_info via TCP.
        :param TCPConnectInfo connect_info:
        :param kwargs: any additional parameters
        :return None:
        """
        self.__try_to_connect_to_addresses(
            connect_info.socket_addresses,
            connect_info.established_callback,
            connect_info.failure_callback,
            **kwargs
        )

    def listen(self, listen_info, **kwargs):
        """
        Listen with network protocol factory on a TCP socket
        specified by listen_info

        :param TCPListenInfo listen_info:
        :param kwargs: any additional parameters
        :return None:
        """
        self.__try_to_listen_on_port(
            listen_info.port_start,
            listen_info.port_end,
            listen_info.established_callback,
            listen_info.failure_callback,
            **kwargs
        )

    def stop_listening(self, listening_info, **kwargs):
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
                    **kwargs
                )
                defer.addErrback(
                    TCPNetwork.__stop_listening_failure,
                    listening_info.stopped_errback,
                    **kwargs
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
                **kwargs,
            )

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

    def __try_to_connect_to_addresses(self, addresses, established_callback,
                                      failure_callback, **kwargs):
        addresses = self.__filter_host_addresses(addresses)
        logger.debug('__try_to_connect_to_addresses(%r) filtered', addresses)

        if not addresses:
            logger.warning("No addresses for connection given")
            TCPNetwork.__call_failure_callback(failure_callback, **kwargs)
            return

        address = addresses[0].address
        port = addresses[0].port

        _args = (
            address, port,
            self.__connection_to_address_established,
            self.__connection_to_address_failure,
        )
        _kwargs = dict(
            addresses_to_arg=addresses,
            established_callback_to_arg=established_callback,
            failure_callback_to_arg=failure_callback,
            **kwargs
        )

        if self.rate_limiter:
            self.rate_limiter.call(self.__try_to_connect_to_address, *_args,
                                   **_kwargs)
        else:
            self.__try_to_connect_to_address(*_args, **_kwargs)

    def __try_to_connect_to_address(self, address, port, established_callback,
                                    failure_callback, **kwargs):
        logger.debug("Connection to host %r: %r", address, port)

        use_ipv6 = False
        try:
            ip = ip_address(address)
            use_ipv6 = ip.version == 6
        except ValueError:
            logger.warning("%r address is invalid", address)
        if use_ipv6:
            endpoint = TCP6ClientEndpoint(self.reactor, address, port,
                                          self.timeout)
        else:
            endpoint = TCP4ClientEndpoint(self.reactor, address, port,
                                          self.timeout)

        defer = endpoint.connect(self.outgoing_protocol_factory)

        defer.addCallback(self.__connection_established, established_callback,
                          **kwargs)
        defer.addErrback(self.__connection_failure, failure_callback, **kwargs)

    def __connection_established(self, conn, established_callback, **kwargs):
        pp = conn.transport.getPeer()
        logger.debug("Connection established %r %r", pp.host, pp.port)
        TCPNetwork.__call_established_callback(
            established_callback,
            conn.session,
            **kwargs,
        )

    def __connection_failure(self, err_desc, failure_callback, **kwargs):
        logger.debug("Connection failure. %r", err_desc)
        TCPNetwork.__call_failure_callback(failure_callback, **kwargs)

    def __connection_to_address_established(self, conn, **kwargs):
        established_callback = kwargs.pop("established_callback_to_arg", None)
        kwargs.pop("failure_callback_to_arg", None)
        kwargs.pop("addresses_to_arg", None)
        TCPNetwork.__call_established_callback(
            established_callback,
            conn,
            **kwargs,
        )

    def __connection_to_address_failure(self, **kwargs):
        established_callback = kwargs.pop("established_callback_to_arg", None)
        failure_callback = kwargs.pop("failure_callback_to_arg", None)
        addresses = kwargs.pop("addresses_to_arg", [])
        if len(addresses) > 1:
            self.__try_to_connect_to_addresses(
                addresses[1:],
                established_callback,
                failure_callback,
                **kwargs,
            )
        else:
            TCPNetwork.__call_failure_callback(failure_callback, **kwargs)

    def __try_to_listen_on_port(self, port, max_port, established_callback,
                                failure_callback, **kwargs):
        if self.use_ipv6:
            ep = TCP6ServerEndpoint(self.reactor, port)
        else:
            ep = TCP4ServerEndpoint(self.reactor, port)

        defer = ep.listen(self.incoming_protocol_factory)

        defer.addCallback(
            self.__listening_established,
            established_callback,
            **kwargs,
        )
        defer.addErrback(
            self.__listening_failure,
            port,
            max_port,
            established_callback,
            failure_callback,
            **kwargs,
        )

    def __listening_established(self, listening_port, established_callback,
                                **kwargs):
        port = listening_port.getHost().port
        self.active_listeners[port] = listening_port
        TCPNetwork.__call_established_callback(
            established_callback,
            port,
            **kwargs,
        )

    def __listening_failure(self, err_desc, port, max_port,
                            established_callback, failure_callback, **kwargs):
        err = str(err_desc.value)
        if port < max_port:
            port += 1
            self.__try_to_listen_on_port(
                port,
                max_port,
                established_callback,
                failure_callback,
                **kwargs,
            )
        else:
            logger.debug("Can't listen on port %r: %r", port, err)
            TCPNetwork.__call_failure_callback(failure_callback, **kwargs)

    @staticmethod
    def __call_failure_callback(failure_callback, **kwargs):
        if failure_callback is None:
            return
        failure_callback(**kwargs)

    @staticmethod
    def __call_established_callback(established_callback, result, **kwargs):
        if established_callback is None:
            return
        established_callback(result, **kwargs)

    @staticmethod
    def __stop_listening_success(result, callback, **kwargs):
        if result:
            logger.info("Stop listening result %r", result)
        if callback is None:
            return
        callback(**kwargs)

    @staticmethod
    def __stop_listening_failure(fail, errback, **kwargs):
        logger.error("Can't stop listening %r", fail)
        TCPNetwork.__call_failure_callback(errback, **kwargs)

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

    def connectionLost(self, reason=ConnectionDone):
        """Called when connection is lost (for whatever reason)"""
        self.opened = False
        if self.session:
            self.session.dropped(reason)

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
