import logging
import ipaddr

from twisted.internet.endpoints import TCP4ServerEndpoint, TCP4ClientEndpoint, TCP6ServerEndpoint, \
    TCP6ClientEndpoint
from twisted.internet.defer import maybeDeferred
from twisted.internet.protocol import connectionDone

from network import Network, SessionProtocol

from golem.core.databuffer import DataBuffer
from golem.Message import Message

logger = logging.getLogger(__name__)


class TCPAddress(object):
    def __init__(self, address, port):
        """
        TCP Address information
        :param str address: address or name
        :param int port:
        :return: None
        """
        self.address = address
        self.port = port

    def __eq__(self, other):
        return self.address == other.address and self.port == other.port


class TCPListenInfo(object):
    def __init__(self, port_start, port_end=None, established_callback=None, failure_callback=None):
        """
        Information needed for listen function. Network will try to start listening on port_start, then iterate
         by 1 to port_end. If port_end is None, than network will only try to listen on port_start.
        :param int port_start: try to start listening from that port
        :param int port_end: *Default: None* highest port that network will try to listen on
        :param fun|None established_callback: *Default: None* deferred callback after listening established
        :param fun|None failure_callback: *Default: None* deferred callback after listening failure
        :return:
        """
        self.port_start = port_start
        if port_end:
            self.port_end = port_end
        else:
            self.port_end = port_start
        self.established_callback = established_callback
        self.failure_callback = failure_callback

    def __str__(self):
        return "TCP listen info: ports [{}:{}], callback: {}, errback: {}".format(self.port_start, self.port_end,
                                                                                  self.established_callback,
                                                                                  self.failure_callback)


class TCPListeningInfo(object):
    def __init__(self, port, stopped_callback=None, stopped_errback=None):
        """
        TCP listening port information
        :param int port: port opened for listening
        :param fun|None stopped_callback: *Default: None* deferred callback after listening on this port is stopped
        :param fun|None stopped_errback: *Default: None* deferred callback after stop listening is failure
        :return:
        """
        self.port = port
        self.stopped_callback = stopped_callback
        self.stopped_errback = stopped_errback

    def __str__(self):
        return "A listening port {} information".format(self.port)


class TCPConnectInfo(object):
    def __init__(self, tcp_addresses,  established_callback=None, failure_callback=None):
        """
        Information for TCP connect function
        :param list tcp_addresses: list of TCPAddresses
        :param fun|None established_callback:
        :param fun|None failure_callback:
        :return None:
        """
        self.tcp_addresses = tcp_addresses
        self.established_callback = established_callback
        self.failure_callback = failure_callback

    def __str__(self):
        return "TCP connection information: addresses {}, callback {}, errback {}".format(self.tcp_addresses,
                                                                                          self.established_callback,
                                                                                          self.failure_callback)


class TCPNetwork(Network):
    def __init__(self, protocol_factory, use_ipv6=False, timeout=5):
        """
        TCP network information
        :param ProtocolFactory protocol_factory: Protocols should be at least ServerProtocol implementation
        :param bool use_ipv6: *Default: False* should network use IPv6 server endpoint?
        :param int timeout: *Default: 5*
        :return None:
        """
        from twisted.internet import reactor
        self.reactor = reactor
        self.protocol_factory = protocol_factory
        self.use_ipv6 = use_ipv6
        self.timeout = timeout
        self.active_listeners = {}

    def connect(self, connect_info, **kwargs):
        """
        Connect network protocol factory to address from connect_info via TCP.
        :param TCPConnectInfo connect_info:
        :param kwargs: any additional parameters
        :return None:
        """
        self.__try_to_connect_to_addresses(connect_info.tcp_addresses, connect_info.established_callback,
                                           connect_info.failure_callback, **kwargs)

    def listen(self, listen_info, **kwargs):
        """
        Listen with network protocol factory on a TCP socket specified by listen_info
        :param TCPListenInfo listen_info:
        :param kwargs: any additional parameters
        :return None:
        """
        self.__try_to_listen_on_port(listen_info.port_start, listen_info.port_end, listen_info.established_callback,
                                     listen_info.failure_callback, **kwargs)

    def stop_listening(self, listening_info, **kwargs):
        """
        Stop listening on a TCP socket specified by litening_info
        :param TCPListeningInfo listening_info:
        :param kwargs: any additional parameters
        :return None|Deferred:
        """
        port = listening_info.port
        listening_port = self.active_listeners.get(port)
        if listening_port:
            defer = maybeDeferred(listening_port.stopListening)

            if not defer.called:
                defer.addCallback(TCPNetwork.__stop_listening_success, listening_info.stopped_callback, **kwargs)
                defer.addErrback(TCPNetwork.__stop_listening_failure, listening_info.stopped_errback, **kwargs)
            del self.active_listeners[port]
            return defer
        else:
            logger.warning("Can't stop listening on port {}, wasn't listening.".format(port))
            TCPNetwork.__stop_listening_failure(None, listening_info.stopped_errback, **kwargs)

    def __try_to_connect_to_addresses(self, addresses, established_callback, failure_callback, **kwargs):
        if len(addresses) == 0:
            logger.warning("No addresses for connection given")
            TCPNetwork.__call_failure_callback(failure_callback, **kwargs)
            return
        address = addresses[0].address
        port = addresses[0].port

        self.__try_to_connect_to_address(address, port, self.__connection_to_address_established,
                                         self.__connection_to_address_failure, addresses_to_arg=addresses,
                                         established_callback_to_arg=established_callback,
                                         failure_callback_to_arg=failure_callback, **kwargs)

    def __try_to_connect_to_address(self, address, port, established_callback, failure_callback, **kwargs):
        logger.debug("Connection to host {}: {}".format(address, port))

        use_ipv6 = False
        try:
            ip = ipaddr.IPAddress(address)
            use_ipv6 = ip.version == 6
        except ValueError:
            logger.warning("{} address is invalid".format(address))
        if use_ipv6:
            endpoint = TCP6ClientEndpoint(self.reactor, address, port, self.timeout)
        else:
            endpoint = TCP4ClientEndpoint(self.reactor, address, port, self.timeout)

        defer = endpoint.connect(self.protocol_factory)

        defer.addCallback(self.__connection_established, established_callback, **kwargs)
        defer.addErrback(self.__connection_failure, failure_callback, **kwargs)

    def __connection_established(self, conn, established_callback, **kwargs):
        pp = conn.transport.getPeer()
        logger.debug("Connection established {} {}".format(pp.host, pp.port))
        TCPNetwork.__call_established_callback(established_callback, conn.session, **kwargs)

    def __connection_failure(self, err_desc, failure_callback, **kwargs):
        logger.info("Connection failure. {}".format(err_desc))
        TCPNetwork.__call_failure_callback(failure_callback, **kwargs)

    def __connection_to_address_established(self, conn, **kwargs):
        established_callback = kwargs.pop("established_callback_to_arg", None)
        kwargs.pop("failure_callback_to_arg", None)
        kwargs.pop("addresses_to_arg", None)
        TCPNetwork.__call_established_callback(established_callback, conn, **kwargs)

    def __connection_to_address_failure(self, **kwargs):
        established_callback = kwargs.pop("established_callback_to_arg", None)
        failure_callback = kwargs.pop("failure_callback_to_arg", None)
        addresses = kwargs.pop("addresses_to_arg", [])
        if len(addresses) > 1:
            self.__try_to_connect_to_addresses(addresses[1:], established_callback, failure_callback, **kwargs)
        else:
            TCPNetwork.__call_failure_callback(failure_callback, **kwargs)

    def __try_to_listen_on_port(self, port, max_port, established_callback, failure_callback, **kwargs):
        if self.use_ipv6:
            ep = TCP6ServerEndpoint(self.reactor, port)
        else:
            ep = TCP4ServerEndpoint(self.reactor, port)

        defer = ep.listen(self.protocol_factory)

        defer.addCallback(self.__listening_established, established_callback, **kwargs)
        defer.addErrback(self.__listening_failure, port, max_port, established_callback, failure_callback, **kwargs)

    def __listening_established(self, listening_port, established_callback, **kwargs):
        port = listening_port.getHost().port
        self.active_listeners[port] = listening_port
        TCPNetwork.__call_established_callback(established_callback, port, **kwargs)

    def __listening_failure(self, err_desc, port, max_port, established_callback, failure_callback, **kwargs):
        err = err_desc.value.message
        if port < max_port:
            port += 1
            self.__try_to_listen_on_port(port, max_port, established_callback, failure_callback, **kwargs)
        else:
            logger.debug("Can't listen on port {}: {}".format(port, err))
            TCPNetwork.__call_failure_callback(failure_callback, **kwargs)

    @staticmethod
    def __call_failure_callback(failure_callback, **kwargs):
        if failure_callback is None:
            return
        if len(kwargs) == 0:
            failure_callback()
        else:
            failure_callback(**kwargs)

    @staticmethod
    def __call_established_callback(established_callback, result, **kwargs):
        if established_callback is None:
            return
        if len(kwargs) == 0:
            established_callback(result)
        else:
            established_callback(result, **kwargs)

    @staticmethod
    def __stop_listening_success(result, callback, **kwargs):
        if result:
            logger.info("Stop listening result {}".format(result))
        if callback is None:
            return
        if len(kwargs) == 0:
            callback()
        else:
            callback(**kwargs)

    @staticmethod
    def __stop_listening_failure(fail, errback, **kwargs):
        logger.error("Can't stop listening {}".format(fail))
        TCPNetwork.__call_failure_callback(errback, **kwargs)


class BasicProtocol(SessionProtocol):
    """ Connection-oriented basic protocol for twisted, support message serialization"""
    def __init__(self):
        SessionProtocol.__init__(self)
        self.opened = False
        self.db = DataBuffer()

    def send_message(self, msg):
        """
        Serialize and send message
        :param Message msg: message to send
        :return bool: return True if message has been send, False if an error has
        """
        if not self.opened:
            logger.error(msg)
            logger.error("Send message failed - connection closed.")
            return False

        msg_to_send = self._prepare_msg_to_send(msg)

        if msg_to_send is None:
            return False

        self.transport.getHandle()
        self.transport.write(msg_to_send)

        return True

    def close(self):
        """
        Close connection, after writing all pending  (flush the write buffer and wait for producer to finish).
        :return None:
        """
        self.transport.loseConnection()

    def close_now(self):
        """
        Close connection ASAP, doesn't flush the write buffer or wait for the producer to finish
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
        """Called when additional chunk of data is received from another peer"""
        if not self._can_receive():
            return None

        if not self.session:
            logger.warning("No session argument in connection state")
            return None

        self._interpret(data)

    def connectionLost(self, reason=connectionDone):
        """Called when connection is lost (for whatever reason)"""
        self.opened = False
        if self.session:
            self.session.dropped()

    # Protected functions
    def _prepare_msg_to_send(self, msg):
        ser_msg = msg.serialize()

        db = DataBuffer()
        db.appendLenPrefixedString(ser_msg)
        return db.readAll()

    def _can_receive(self):
        return self.opened and isinstance(self.db, DataBuffer)

    def _interpret(self, data):
        self.db.appendString(data)
        mess = self._data_to_messages()
        if mess is None or len(mess) == 0:
            logger.error("Deserialization message failed")
            return None

        for m in mess:
            self.session.interpret(m)

    def _data_to_messages(self):
        return Message.deserialize(self.db)


class ServerProtocol(BasicProtocol):
    """ Basic protocol connected to server instance
    """
    def __init__(self, server):
        """
        :param Server server: server respon
        :return None:
        """
        BasicProtocol.__init__(self)
        self.server = server

    # Protocol functions
    def connectionMade(self):
        """Called when new connection is successfully opened"""
        BasicProtocol.connectionMade(self)
        self.server.new_connection(self.session)

    def _can_receive(self):
        assert self.opened
        assert isinstance(self.db, DataBuffer)

        if not self.session and self.server:
            self.opened = False
            raise Exception('Peer for connection is None')

        return True


class SafeProtocol(ServerProtocol):
    """More advanced version of server protocol, support for serialization, encryption, decryption and signing
    messages """

    def _prepare_msg_to_send(self, msg):
        if self.session is None:
            logger.error("Wrong session, not sending message")
            return None

        msg = self.session.sign(msg)
        if not msg:
            logger.error("Wrong session, not sending message")
            return None
        ser_msg = msg.serialize()
        enc_msg = self.session.encrypt(ser_msg)

        db = DataBuffer()
        db.appendLenPrefixedString(enc_msg)
        return db.readAll()

    def _data_to_messages(self):
        assert isinstance(self.db, DataBuffer)
        msgs = [msg for msg in self.db.getLenPrefixedString()]
        messages = []
        for msg in msgs:
            dec_msg = self.session.decrypt(msg)
            if dec_msg is None:
                logger.warning("Decryption of message failed")
                return None
            m = Message.deserializeMessage(dec_msg)
            if m is None:
                return None
            m.encrypted = dec_msg != msg
            messages.append(m)
        return messages
