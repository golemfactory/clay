import logging
import os
import re
import struct
import time
from copy import copy
from threading import Lock

from golem.core.hostaddress import get_host_addresses
from twisted.internet.defer import maybeDeferred
from twisted.internet.endpoints import TCP4ServerEndpoint, TCP4ClientEndpoint, TCP6ServerEndpoint, \
    TCP6ClientEndpoint
from twisted.internet.interfaces import IPullProducer
from twisted.internet.protocol import connectionDone
from zope.interface import implements

from ipaddress import IPv6Address, IPv4Address, ip_address, AddressValueError

from golem.core.databuffer import DataBuffer
from golem.core.variables import LONG_STANDARD_SIZE, BUFF_SIZE, MIN_PORT, MAX_PORT
from golem.network.transport.message import Message
from network import Network, SessionProtocol

logger = logging.getLogger(__name__)

##########################
# Network helper classes #
##########################


class SocketAddress(object):
    """TCP socket address (host and port)"""

    _dns_label_pattern = re.compile('(?!-)[a-z\d-]{1,63}(?<!-)\Z', re.IGNORECASE)
    _all_numeric_pattern = re.compile('[0-9\.]+\Z')

    @classmethod
    def is_proper_address(cls, address, port):
        try:
            SocketAddress(address, port)
        except (AddressValueError, TypeError) as err:
            logger.info("Wrong address {}".format(err))
            return False
        return True

    def __init__(self, address, port):
        """Creates and validates SocketAddress. Raises
        AddressValueError if 'address' or 'port' is invalid.
        :param str address: IPv4/IPv6 address or hostname
        :param int port:
        """
        self.address = address
        self.port = port
        self.ipv6 = False
        try:
            self.__validate()
        except ValueError, err:
            raise AddressValueError(err.message)

    def __validate(self):
        if type(self.address) is unicode:
            self.address = self.address.encode()
        if type(self.address) is not str:
            raise TypeError('Address must be a string, not a ' +
                            type(self.address).__name__)
        if type(self.port) is not int and type(self.port) is not long:
            raise TypeError('Port must be an int, not a ' +
                            type(self.port).__name__)

        if self.address.find(':') != -1:
            # IPv6 address
            if self.address.find("%") != -1:
                # Address with zone index
                self.address = self.address[:self.address.find("%")]

            IPv6Address(self.address.decode('utf8'))
            self.ipv6 = True
        else:
            # If it's all digits then guess it's an IPv4 address
            if self._all_numeric_pattern.match(self.address):
                IPv4Address(self.address.decode('utf8'))
            else:
                SocketAddress.validate_hostname(self.address)

        if not (MIN_PORT <= self.port <= MAX_PORT):
            raise ValueError('Port out of range ({} .. {}): {}'.format(
                MIN_PORT, MAX_PORT, self.port))

    def __eq__(self, other):
        return self.address == other.address and self.port == other.port

    def __repr__(self):
        return "SocketAddress(%r, %r)" % (self.address, self.port)

    def __str__(self):
        return self.address + ":" + str(self.port)

    @staticmethod
    def validate_hostname(hostname):
        """Checks that the given string is a valid hostname.
        See RFC 1123, page 13, and here:
        http://stackoverflow.com/questions/2532053/validate-a-hostname-string.
        Raises ValueError if the argument is not a valid hostname.
        :param str hostname:
        :returns None
        """
        if type(hostname) is unicode:
            hostname = hostname.encode()

        if type(hostname) is not str:
            raise TypeError('Expected string argument, not ' +
                            type(hostname).__name__)

        if hostname == '':
            raise ValueError('Empty host name')
        if len(hostname) > 255:
            raise ValueError('Host name exceeds 255 chars: ' + hostname)
        # Trailing '.' is allowed!
        if hostname.endswith('.'):
            hostname = hostname[:-1]
        segments = hostname.split('.')
        if not all(SocketAddress._dns_label_pattern.match(s) for s in segments):
            raise ValueError('Invalid host name: ' + hostname)

    @staticmethod
    def parse(string):
        """Parses a string representation of a socket address.
        IPv4 syntax: <IPv4 address> ':' <port>
        IPv6 syntax: '[' <IPv6 address> ']' ':' <port>
        DNS syntax:  <hostname> ':' <port>
        Raises AddressValueError if the input cannot be parsed.
        :param str string:
        :returns parsed SocketAddress
        :rtype SocketAddress
        """
        if type(string) is unicode:
            string = string.encode()

        if type(string) is not str:
            raise TypeError('Expected string argument, not ' +
                            type(string).__name__)

        try:
            if string.startswith('['):
                # We expect '[<ip6 addr>]:<portnum>',
                # use ipaddress to parse IPv6 address:
                addr_str, port_str = string.split(']:')
                addr_str = addr_str[1:]
            else:
                # We expect '<ip4 addr or hostname>:<port>'.
                addr_str, port_str = string.split(':')
            port = int(port_str)
        except ValueError:
            raise AddressValueError('Invalid address: port missing or invalid')

        return SocketAddress(addr_str, port)


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
    def __init__(self, socket_addresses,  established_callback=None, failure_callback=None):
        """
        Information for TCP connect function
        :param list socket_addresses: list of SocketAddresses
        :param fun|None established_callback:
        :param fun|None failure_callback:
        :return None:
        """
        self.socket_addresses = socket_addresses
        self.established_callback = established_callback
        self.failure_callback = failure_callback

    def __str__(self):
        return "TCP connection information: addresses {}, callback {}, errback {}".format(self.socket_addresses,
                                                                                          self.established_callback,
                                                                                          self.failure_callback)

###############
# TCP Network #
###############


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
        self.host_addresses = get_host_addresses()

    def connect(self, connect_info, **kwargs):
        """
        Connect network protocol factory to address from connect_info via TCP.
        :param TCPConnectInfo connect_info:
        :param kwargs: any additional parameters
        :return None:
        """
        self.__try_to_connect_to_addresses(connect_info.socket_addresses, connect_info.established_callback,
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
                defer.addCallback(TCPNetwork.__stop_listening_success, listening_info.stopped_callback, **kwargs)
                defer.addErrback(TCPNetwork.__stop_listening_failure, listening_info.stopped_errback, **kwargs)
            del self.active_listeners[port]
            return defer
        else:
            logger.warning("Can't stop listening on port {}, wasn't listening.".format(port))
            TCPNetwork.__stop_listening_failure(None, listening_info.stopped_errback, **kwargs)

    def __filter_host_addresses(self, addresses):
        result = []

        for sa in addresses:
            if not (sa.address in self.host_addresses and sa.port in self.active_listeners):
                result.append(sa)
        return result

    def __try_to_connect_to_addresses(self, addresses, established_callback, failure_callback, **kwargs):
        addresses = self.__filter_host_addresses(addresses)

        if len(addresses) == 0:
            logger.warning("No addresses for connection given")
            TCPNetwork.__call_failure_callback(failure_callback, **kwargs)
            return

        address = addresses[0].address
        port = addresses[0].port

        self.__try_to_connect_to_address(address, port,
                                         self.__connection_to_address_established,
                                         self.__connection_to_address_failure,
                                         addresses_to_arg=addresses,
                                         established_callback_to_arg=established_callback,
                                         failure_callback_to_arg=failure_callback,
                                         **kwargs)

    def __try_to_connect_to_address(self, address, port, established_callback, failure_callback, **kwargs):
        logger.debug("Connection to host {}: {}".format(address, port))

        use_ipv6 = False
        try:
            ip = ip_address(address.decode())
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

#############
# Protocols #
#############


class BasicProtocol(SessionProtocol):

    """ Connection-oriented basic protocol for twisted, support message serialization"""
    def __init__(self):
        self.opened = False
        self.db = DataBuffer()
        self.lock = Lock()
        SessionProtocol.__init__(self)

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

        SessionProtocol.connectionLost(self, reason)

    # Protected functions
    def _prepare_msg_to_send(self, msg):
        ser_msg = msg.serialize()

        db = DataBuffer()
        db.append_len_prefixed_string(ser_msg)
        return db.read_all()

    def _can_receive(self):
        return self.opened and isinstance(self.db, DataBuffer)

    def _interpret(self, data):
        with self.lock:
            self.db.append_string(data)
            mess = self._data_to_messages()

        # Interpret messages
        if mess:
            for m in mess:
                self.session.interpret(m)
        elif data:
            logger.info("Deserialization of messages from {}:{} failed, maybe it's still "
                        "too short?".format(self.session.address, self.session.port))

    def _data_to_messages(self):
        return Message.deserialize(self.db)


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

    def _can_receive(self):
        if not self.opened:
            raise IOError("Protocol is closed")
        if not isinstance(self.db, DataBuffer):
            raise TypeError("incorrect db type: {}. Should be: DataBuffer".format(type(self.db)))

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
        db.append_len_prefixed_string(enc_msg)
        return db.read_all()

    def _data_to_messages(self):
        if not isinstance(self.db, DataBuffer):
            raise TypeError("incorrect db type: {}. Should be: DataBuffer".format(type(self.db)))
        messages = []

        for msg in self.db.get_len_prefixed_string():
            dec_msg = self.session.decrypt(msg)
            if not dec_msg:
                logger.warning("Decryption of message failed")
                break

            m = Message.deserialize_message(dec_msg)
            if not m:
                logger.warning("Deserialization of message failed")
                break

            m.encrypted = dec_msg != msg
            messages.append(m)

        return messages


class FilesProtocol(SafeProtocol):
    """ Connection-oriented protocol for twisted. Allows to send messages (support for message serialization)
    encryption, decryption and signing), files or stream data."""
    def __init__(self, server=None):
        SafeProtocol.__init__(self, server)

        self.stream_mode = False
        self.consumer = None
        self.producer = None

    def clean(self):
        """ Clean the protocol state. Close existing consumers and producers."""
        if self.consumer is not None:
            self.consumer.close()

        if self.producer is not None:
            self.producer.close()

    def close(self):
        """ Close connection, after writing all pending  (flush the write buffer and wait for producer to finish).
        Close file consumer, data consumer or file producer if they are active.
        :return None: """
        self.clean()
        SafeProtocol.close(self)

    def close_now(self):
        """ Close connection ASAP, doesn't flush the write buffer or wait for the producer to finish.
        Close file consumer, data consumer or file producer if they are active. """
        self.opened = False
        self.clean()
        SafeProtocol.close_now(self)

    def _interpret(self, data):
        self.session.last_message_time = time.time()

        if self.stream_mode:
            self._stream_data_received(data)
            return

        SafeProtocol._interpret(self, data)

    def _stream_data_received(self, data):
        if self.consumer is None:
            raise ValueError("consumer is None")
        if self._check_stream(data):
            self.consumer.dataReceived(data)
        else:
            logger.error("Wrong stream received")
            self.close_now()

    def _check_stream(self, data):
        return len(data) >= LONG_STANDARD_SIZE


class MidAndFilesProtocol(FilesProtocol):
    """ Connection-oriented protocol for twisted. In the Middleman mode pass message to session without
    decrypting or deserializing it. In normal mode allows to send messages (support for message serialization)
    encryption, decryption and signing), files or stream data."""
    def _interpret(self, data):
        if self.session.is_middleman:
            self.session.last_message_time = time.time()
            with self.lock:
                self.db.append_string(data, check_size=False)
                messages = self.db.read_all()
            self.session.interpret(messages)
        else:
            FilesProtocol._interpret(self, data)

    ############################
    def _prepare_msg_to_send(self, msg):
        if self.session.is_middleman:
            return msg
        else:
            return FilesProtocol._prepare_msg_to_send(self, msg)

#############
# Producers #
#############


class FileProducer(object):
    """ Files producer that helps to send list of files to consumer in chunks"""

    implements(IPullProducer)

    def __init__(self, file_list, session, buff_size=BUFF_SIZE, extra_data=None):
        """ Create file producer
        :param list file_list: list of files that should be sent
        :param FileSession session:  session that uses this file producer
        :param int buff_size: size of the buffer
        :param dict extra_data: additional information that should be return to the session
        """
        self.file_list = copy(file_list)
        self.session = session
        self.buff_size = buff_size

        if extra_data:
            self.extra_data = extra_data
        else:
            self.extra_data = {}
        self.extra_data['file_sent'] = []
        self.extra_data['file_sizes'] = []
        self.cnt = 0

        self.fh = None  # Current file descriptor
        self.data = None  # Current chunk of data
        self.size = 0  # Size of current file

        self.init_data()
        self.register()

    # IPullProducer methods
    def resumeProducing(self):
        """ Produce data for the consumer a single time. Send a chunk of file, open new file or finish productions.
        """

        if self.data:
            self.session.conn.transport.write(self.data)
            self._print_progress()
            self._prepare_data()
        elif len(self.file_list) > 1:
            if self.fh is not None:
                self.fh.close()
                self.fh = None
            self.extra_data['file_sent'].append(self.file_list[-1])
            self.file_list.pop()
            self.init_data()
            self.resumeProducing()
        else:
            if self.fh is not None:
                self.fh.close()
                self.fh = None
            self.session.data_sent(self.extra_data)
            self.session.conn.transport.unregisterProducer()

    def stopProducing(self):
        """ Stop producing data. This tells a producer that its consumer has died, so it must stop producing data
        for good. """
        self.close()
        self.session.production_failed(self.extra_data)

    def init_data(self):
        """  Open first file from list and read first chunk of data """
        if len(self.file_list) == 0:
            logger.warning("Empty file list to send")
            self.data = None
            return
        self.fh = open(self.file_list[-1], 'rb')
        self.size = os.path.getsize(self.file_list[-1])
        self.extra_data['file_sizes'].append(self.size)
        logger.info("Sending file {}, size:{}".format(self.file_list[-1], self.size))
        self._prepare_init_data()

    def register(self):
        """ Register producer """
        self.session.conn.transport.registerProducer(self, False)

    def close(self):
        """ Close file descriptor"""
        if self.fh is not None:
            self.fh.close()
            self.fh = None

    def _prepare_init_data(self):
        self.data = struct.pack("!L", self.size) + self.fh.read(self.buff_size)

    def _prepare_data(self):
        self.data = self.fh.read(self.buff_size)

    def _print_progress(self):
        if self.size != 0:
            print "\rSending progress {} %                       ".format(int(100 * float(self.fh.tell()) / self.size)),
        else:
            print "\rSending progress 100 %                       ",


class EncryptFileProducer(FileProducer):
    """ Files producer that encrypt data chunks """

    def _prepare_init_data(self):
        data = self.session.encrypt(self.fh.read(self.buff_size))
        self.data = struct.pack("!L", self.size) + struct.pack("!L", len(data)) + data

    def _prepare_data(self):
        data = self.fh.read(self.buff_size)
        if data:
            data = self.session.encrypt(data)
            self.data = struct.pack("!L", len(data)) + data
        else:
            self.data = ""


class FileConsumer(object):
    """ File consumer that receives list of files in chunks"""

    def __init__(self, file_list, output_dir, session, extra_data=None):
        """
        Create file consumer
        :param list file_list: names of files to received
        :param str output_dir: name of the directory where received files should be saved
        :param FileSession session: session that uses this file consumer
        :param dict extra_data: additional information that should be return to the session
        :return:
        """
        self.file_list = copy(file_list)

        self.final_file_list = [os.path.normpath(os.path.join(output_dir, f)) for f in file_list]
        self.fh = None  # Current file descriptor
        self.file_size = -1  # Current file expected size
        self.recv_size = 0  # Received data size

        self.output_dir = output_dir

        self.session = session
        if extra_data:
            self.extra_data = extra_data
        else:
            self.extra_data = {}
        self.extra_data["file_received"] = []
        self.extra_data["file_sizes"] = []
        self.extra_data["result"] = self.final_file_list

        self.last_percent = 0
        self.last_data = ""

    def dataReceived(self, data):
        """ Receive new chunk of data
        :param data: data received with transport layer
        """
        loc_data = data
        if self.file_size == -1:
            loc_data = self._get_first_chunk(self.last_data + data)

        if not self.fh:
            raise ValueError("File descriptor is not set")

        self.recv_size += len(loc_data)
        if self.recv_size <= self.file_size:
            self.fh.write(loc_data)
            self.last_data = ""
        else:
            last_data = len(loc_data) - (self.recv_size - self.file_size)
            self.fh.write(loc_data[:last_data])
            self.last_data = loc_data[last_data:]

        self._print_progress()

        if self.recv_size >= self.file_size:
            self._end_receiving_file()

    def close(self):
        """ Close file descriptor and remove file if not all data were received
        """
        if self.fh is not None:
            self.fh.close()
            self.fh = None
            if self.recv_size < self.file_size and len(self.file_list) > 0:
                os.remove(self.file_list[-1])

    def _get_first_chunk(self, data):
        self.last_percent = 0
        (self.file_size,) = struct.unpack("!L", data[:LONG_STANDARD_SIZE])
        logger.info("Receiving file {}, size {}".format(self.file_list[-1], self.file_size))
        if self.fh:
            raise ValueError("File descriptor is set")

        self.extra_data["file_sizes"].append(self.file_size)
        self.fh = open(os.path.join(self.output_dir, self.file_list[-1]), "wb")
        return data[LONG_STANDARD_SIZE:]

    def _print_progress(self):
        if self.file_size != 0:
            percent = int(100 * self.recv_size / float(self.file_size))
        else:
            percent = 100
        if percent > 100:
            percent = 100
        if percent > self.last_percent:
            print "\rFile data receiving {} %                       ".format(percent),
            self.last_percent = percent

    def _end_receiving_file(self):
        self.fh.close()
        self.fh = None
        self.extra_data["file_received"].append(self.file_list[-1])
        self.file_list.pop()
        self.recv_size = 0
        self.file_size = -1
        if len(self.file_list) == 0:
            self.session.conn.file_mode = False
            self.session.full_data_received(extra_data=self.extra_data)


class DecryptFileConsumer(FileConsumer):
    """ File consumer that receives list of files in encrypted chunks """

    def __init__(self, file_list, output_dir, session, extra_data=None):
        """
        Create file consumer
        :param list file_list: names of files to received
        :param str output_dir: name of the directory where received files should be saved
        :param FileSession session: session that uses this file consumer
        :param dict extra_data: additional information that should be return to the session
        :return:
        """
        FileConsumer.__init__(self, file_list, output_dir, session, extra_data)
        self.chunk_size = 0
        self.recv_chunk_size = 0

    def dataReceived(self, data):
        """ Receive new chunk of data
        :param data: data received with transport layer
        """
        loc_data = self.last_data + data
        if self.file_size == -1:
            loc_data = self._get_first_chunk(loc_data)

        if not self.fh:
            raise ValueError("File descriptor is not set")

        receive_next = False
        while not receive_next:
            if self.chunk_size == 0:
                (self.chunk_size,) = struct.unpack("!L", loc_data[:LONG_STANDARD_SIZE])
                loc_data = loc_data[LONG_STANDARD_SIZE:]

            self.recv_chunk_size = len(loc_data)
            if self.recv_chunk_size >= self.chunk_size:
                data = self.session.decrypt(loc_data[:self.chunk_size])
                self.fh.write(data)
                self.recv_size += len(data)
                self.last_data = loc_data[self.chunk_size:]
                self.recv_chunk_size = 0
                self.chunk_size = 0
                loc_data = self.last_data
                if len(self.last_data) <= LONG_STANDARD_SIZE:
                    receive_next = True
            else:
                self.last_data = loc_data
                receive_next = True

            self._print_progress()

            if self.recv_size >= self.file_size:
                self._end_receiving_file()
                receive_next = True
        if len(self.file_list) > 0 and len(self.last_data) >= 2 * LONG_STANDARD_SIZE and self.chunk_size == 0:
            self.dataReceived("")

    def _end_receiving_file(self):
        self.chunk_size = 0
        self.recv_chunk_size = 0
        FileConsumer._end_receiving_file(self)


class DataProducer(object):
    """ Data producer that helps to receive stream of data in chunks"""

    implements(IPullProducer)

    def __init__(self, data_to_send, session, buff_size=BUFF_SIZE, extra_data=None):
        """ Create data producer
        :param str data_to_send: data that should be send
        :param FileSession session:  session that uses this file producer
        :param int buff_size: size of the buffer
        :param dict extra_data: additional information that should be return to the session
        """
        self.data_to_send = data_to_send
        self.session = session
        self.data = None  # current chunk of data
        self.size = 0  # size of data that will be send
        self.it = 0  # data to send iterator
        self.num_send = 0  # size of sent data
        self.extra_data = extra_data
        self.buff_size = buff_size
        self.last_percent = 0
        self.load_data()
        self.register()

    def load_data(self):
        """ Load first chunk of data """
        self.size = len(self.data_to_send)
        logger.info("Sending file size:{}".format(self.size))
        self._prepare_init_data()
        self.it = self.buff_size

    def register(self):
        """ Register producer """
        self.session.conn.transport.registerProducer(self, False)

    def end_producing(self):
        """ Inform session about finished production and unregister producer """
        self.session.data_sent(self.extra_data)
        self.session.conn.transport.unregisterProducer()

    def close(self):
        """ Additional cleaning before production ending """
        pass

    # IPullProducer methods
    def resumeProducing(self):
        """ Produce data for the consumer a single time. Send a chunk of data or finish productions. """
        if self.data:
            self.session.conn.transport.write(self.data)
            self.num_send += len(self.data)
            self._print_progress()

            if self.it < len(self.data_to_send):
                self._prepare_data()
                self.it += self.buff_size
            else:
                self.data = None
                self.end_producing()
        else:
            self.end_producing()

    def stopProducing(self):
        """ Stop producing data. This tells a producer that its consumer has died, so it must stop producing data
        for good. """
        self.close()
        self.session.production_failed(self.extra_data)

    def _print_progress(self):
        if self.size != 0:
            percent = int(100 * float(self.num_send) / self.size)
        else:
            percent = 100
        if percent > self.last_percent:
            print "\rSending progress {} %                       ".format(percent),
        self.last_percent = percent

    def _prepare_init_data(self):
        self.data = struct.pack("!L", self.size) + self.data_to_send[:self.buff_size]
        self.num_send -= LONG_STANDARD_SIZE

    def _prepare_data(self):
        self.data = self.data_to_send[self.it:self.it + self.buff_size]


class DataConsumer(object):
    """ Data consumer that receive stream of data in chunks """

    def __init__(self, session, extra_data):
        """ Create data consumer
        :param FileSession session: session that uses this file consumer
        :param dict extra_data: additional information that should be return to the session
        :return:
        """
        self.loc_data = []  # received data chunks
        self.data_size = -1  # size of file to receive
        self.recv_size = 0  # size of received data

        self.session = session
        self.extra_data = extra_data

        self.last_percent = 0

    def dataReceived(self, data):
        """ Receive new chunk of data
        :param data: data received with transport layer
        """
        if self.data_size == -1:
            self.loc_data.append(self._get_first_chunk(data))
            self.recv_size = len(self.loc_data[-1])
        else:
            self.loc_data.append(data)
            self.recv_size += len(data)

        self._print_progress()

        if self.recv_size == self.data_size:
            self._end_receiving()

    def close(self):
        """ Clean data if it's needed """
        pass

    def _get_first_chunk(self, data):
        self.last_percent = 0
        (self.data_size,) = struct.unpack("!L", data[:LONG_STANDARD_SIZE])
        logger.debug("Receiving data size {}".format(self.data_size))
        return data[LONG_STANDARD_SIZE:]

    def _print_progress(self):
        if self.data_size != 0:
            percent = int(100 * self.recv_size / float(self.data_size))
        else:
            percent = 100
        if percent > self.last_percent:
            print "\rFile data receiving {} %                       ".format(percent),
            self.last_percent = percent

    def _end_receiving(self):
        self.session.conn.data_mode = False
        self.data_size = -1
        self.recv_size = 0
        self.extra_data["result"] = "".join(self.loc_data)
        self.loc_data = []
        self.session.full_data_received(extra_data=self.extra_data)


class EncryptDataProducer(DataProducer):
    """ Data producer that encrypt data chunks """

    # IPullProducer methods
    def resumeProducing(self):
        if self.data:
            self.session.conn.transport.write(self.data)
            self._print_progress()

            if self.it < len(self.data_to_send):
                self._prepare_data()
                self.it += self.buff_size
            else:
                self.data = None
                self.end_producing()
        else:
            self.end_producing()

    def _prepare_init_data(self):
        data = self.session.encrypt(self.data_to_send[:self.buff_size])
        self.data = struct.pack("!L", self.size) + struct.pack("!L", len(data)) + data
        self.num_send += len(self.data_to_send[:self.buff_size])

    def _prepare_data(self):
        data = self.session.encrypt(self.data_to_send[self.it:self.it + self.buff_size])
        self.data = struct.pack("!L", len(data)) + data
        self.num_send += len(self.data_to_send[self.it:self.it + self.buff_size])


class DecryptDataConsumer(DataConsumer):
    """ Data consumer that receives data in encrypted chunks """
    def __init__(self, session, extra_data):
        self.chunk_size = 0
        self.recv_chunk_size = 0
        self.last_data = ""
        DataConsumer.__init__(self, session, extra_data)

    def dataReceived(self, data):
        """ Receive new chunk of encrypted data
        :param data: data received with transport layer
        """

        loc_data = self.last_data + data
        if self.data_size == -1:
            loc_data = self._get_first_chunk(data)

        receive_next = False
        while not receive_next:
            if self.chunk_size == 0:
                (self.chunk_size,) = struct.unpack("!L", loc_data[:LONG_STANDARD_SIZE])
                loc_data = loc_data[LONG_STANDARD_SIZE:]

            self.recv_chunk_size = len(loc_data)
            if self.recv_chunk_size >= self.chunk_size:
                data = self.session.decrypt(loc_data[:self.chunk_size])
                self.loc_data.append(data)
                self.recv_size += len(data)
                self.last_data = loc_data[self.chunk_size:]
                self.recv_chunk_size = 0
                self.chunk_size = 0
                loc_data = self.last_data
                if len(self.last_data) <= LONG_STANDARD_SIZE:
                    receive_next = True
            else:
                self.last_data = loc_data
                receive_next = True

            self._print_progress()

            if self.recv_size >= self.data_size:
                self._end_receiving()
                break

    def _end_receiving(self):
        self.chunk_size = 0
        self.recv_chunk_size = 0
        DataConsumer._end_receiving(self)
