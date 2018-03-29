import ipaddress
import logging
import re
import uuid
from functools import partial
from typing import Callable, List, Optional

from golem.core.types import Kwargs
from golem.core import variables

logger = logging.getLogger(__name__)

##########################
# Network helper classes #
##########################


class SocketAddress():
    """TCP socket address (host and port)"""

    _dns_label_pattern = re.compile(
        r'(?!-)[a-z\d-]{1,63}(?<!-)\Z',
        re.IGNORECASE,
    )
    _all_numeric_pattern = re.compile(r'[0-9\.]+\Z')

    @classmethod
    def is_proper_address(cls, address, port):
        try:
            SocketAddress(address, port)
        except Exception as exc:  # pylint: disable=broad-except
            logger.info("Wrong address %r", exc)
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
        self.hostname = False
        try:
            self.__validate()
        except ValueError as err:
            raise ipaddress.AddressValueError(err)

    def __validate(self):
        if isinstance(self.address, str):
            self.address = self.address
        else:
            raise TypeError('Address must be a string, not a ' +
                            type(self.address).__name__)
        if not isinstance(self.port, int):
            raise TypeError('Port must be an int, not a ' +
                            type(self.port).__name__)

        if self.address.find(':') != -1:
            # IPv6 address
            if self.address.find("%") != -1:
                # Address with zone index
                self.address = self.address[:self.address.find("%")]

            ipaddress.IPv6Address(self.address)
            self.ipv6 = True
        else:
            # If it's all digits then guess it's an IPv4 address
            if self._all_numeric_pattern.match(self.address):
                ipaddress.IPv4Address(self.address)
            else:
                SocketAddress.validate_hostname(self.address)
                self.hostname = True

        if not variables.MIN_PORT <= self.port <= variables.MAX_PORT:
            raise ValueError('Port out of range ({} .. {}): {}'.format(
                variables.MIN_PORT, variables.MAX_PORT, self.port))

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
        if not isinstance(hostname, str):
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

        if not isinstance(string, str):
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
            raise ipaddress.AddressValueError(
                'Invalid address "{}"'.format(string))

        return SocketAddress(addr_str, port)


class TCPListenInfo(object):
    def __init__(self,
                 port_start: int,
                 port_end: Optional[int] = None,
                 established_callback: Optional[Callable] = None,
                 failure_callback: Optional[Callable] = None) \
                 -> None:
        """
        Information needed for listen function. Network will try to start
        listening on port_start, then iterate by 1 to port_end.
        If port_end is None, than network will only try to listen on
        port_start.
        :param port_start: try to start listening from that port
        :param port_end: *Default: None* highest port that network will try to
                         listen on
        :param established_callback: *Default: None* deferred callback after
                                     listening established
        :param failure_callback: *Default: None* deferred callback after
                                 listening failure
        :return:
        """
        self.port_start = port_start
        self.port_end = port_end if port_end else port_start
        self.established_callback = established_callback
        self.failure_callback = failure_callback

    def __str__(self):
        return ("TCP listen info: ports [{}:{}],"
                "callback: {}, errback: {}").format(
                    self.port_start,
                    self.port_end,
                    self.established_callback,
                    self.failure_callback, )


class TCPListeningInfo(object):
    def __init__(self,
                 port: int,
                 stopped_callback: Optional[Callable] = None,
                 stopped_errback: Optional[Callable] = None) \
                 -> None:
        """
        TCP listening port information
        :param port: port opened for listening
        :param stopped_callback: *Default: None* deferred callback after
                                 listening on this port is stopped
        :param stopped_errback: *Default: None* deferred callback after stop
                                listening failed
        """
        self.port = port
        self.stopped_callback = stopped_callback
        self.stopped_errback = stopped_errback

    def __str__(self):
        return "A listening port {} information".format(self.port)


class TCPConnectInfo(object):
    # pylint: disable-msg=too-many-arguments
    def __init__(self,
                 socket_addresses: List[SocketAddress],
                 established_callback: Optional[Callable] = None,
                 failure_callback: Optional[Callable] = None,
                 final_failure_callback: Optional[Callable] = None,
                 kwargs: Kwargs = dict()) \
                 -> None:
        """
        Information for TCP connect function
        """
        self.id = str(uuid.uuid4())
        self.socket_addresses = socket_addresses
        self.established_callback = (
            partial(established_callback, conn_id=self.id, **kwargs)
            if established_callback else None)
        self.failure_callback = (
            partial(failure_callback, conn_id=self.id, **kwargs)
            if failure_callback else None)
        self.final_failure_callback = (
            partial(final_failure_callback, conn_id=self.id, **kwargs)
            if final_failure_callback else None)

    def __str__(self):
        return ("TCP connection information: addresses {}, "
                "callback {}, errback {}, final_errback {}").format(
                    self.socket_addresses,
                    self.established_callback.func,
                    self.failure_callback.func,
                    self.final_failure_callback.func)
