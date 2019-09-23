import logging
import time
from typing import Callable, Dict, List, Optional, Set

from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.common import node_info_str
from golem.core.types import Kwargs
from golem.core.hostaddress import ip_address_private, ip_network_contains, \
    ipv4_networks
from golem.core.variables import MAX_CONNECT_SOCKET_ADDRESSES

from .session import BasicSession
from .tcpnetwork import TCPNetwork, TCPListeningInfo, TCPListenInfo, \
    SocketAddress, TCPConnectInfo

logger = logging.getLogger(__name__)


class TCPServer:
    """ Basic tcp server that can start listening on given port """

    def __init__(self,
                 config_desc: ClientConfigDescriptor,
                 network: TCPNetwork) -> None:
        """
        Create new server
        :param config_desc: config descriptor for listening port
        :param network: network that server will use
        """
        self.config_desc = config_desc
        self.network = network
        # Start inactive to prevent receiving messages before the node is ready
        self.active = False
        self.cur_port = 0  # current listening port
        self.use_ipv6 = config_desc.use_ipv6 if config_desc else False
        self.ipv4_networks = ipv4_networks()

    def change_config(self, config_desc: ClientConfigDescriptor):
        """ Change configuration descriptor. If listening port is changed, than stop listening on old port and start
        listening on a new one.
        :param config_desc: new config descriptor
        """
        self.config_desc = config_desc
        if (self.config_desc.start_port or 0) \
                <= self.cur_port <= (self.config_desc.end_port or 0):
            return

        if self.cur_port != 0:
            listening_info = TCPListeningInfo(
                self.cur_port,
                self._stopped_callback,
                self._stopped_errback,
            )
            self.network.stop_listening(listening_info)

        self.start_accepting()

    def start_accepting(self, listening_established=None, listening_failure=None):
        """ Start listening and accept connections """
        def established(port):
            self._listening_established(port)
            if listening_established:
                listening_established(port)

        def failure():
            self._listening_failure()
            if listening_failure:
                listening_failure()

        listen_info = TCPListenInfo(self.config_desc.start_port,
                                    self.config_desc.end_port,
                                    established, failure)
        self.network.listen(listen_info)

    def stop_accepting(self):
        if self.network and self.cur_port:
            self.network.stop_listening(TCPListeningInfo(self.cur_port))
            self.cur_port = None

    def pause(self):
        self.active = False

    def resume(self):
        self.active = True

    def _stopped_callback(self):
        logger.debug("Stopped listening on previous port")

    def _stopped_errback(self):
        logger.debug("Failed to stop listening on previous port")

    def _listening_established(self, port):
        self.cur_port = port
        logger.debug("Port {} opened - listening.".format(self.cur_port))

    def _listening_failure(self):
        logger.error("Listening on ports {} to {} failure.".format(self.config_desc.start_port,
                                                                   self.config_desc.end_port))


class PendingConnectionsServer(TCPServer):
    """ TCP Server that keeps a list of pending connections and tries different methods
    if connection attempt is unsuccessful."""

    def __init__(self,
                 config_desc: ClientConfigDescriptor,
                 network: TCPNetwork) -> None:
        """ Create new server
        :param config_desc: config descriptor for listening port
        :param network: network that server will use
        """
        # Pending connections
        #  Connections that should be accomplished
        self.pending_connections: Dict[str, PendingConnection] = {}
        #  Sessions a.k.a Peers before handshake
        self.pending_sessions: Set[BasicSession] = set()
        #  Reactions for established connections of certain types
        self.conn_established_for_type: Dict[int, Callable] = {}
        #  Reactions for failed connection attempts of certain types
        self.conn_failure_for_type: Dict[int, Callable] = {}
        #  Reactions for final connection attempts failure
        self.conn_final_failure_for_type: Dict[int, Callable] = {}

        # Set reactions
        self._set_conn_established()
        self._set_conn_failure()
        self._set_conn_final_failure()

        TCPServer.__init__(self, config_desc, network)

    def verified_conn(self, conn_id):
        """ React to the information that connection was established and verified, remove given connection from
        pending connections list.
        :param uuid|None conn_id: id of verified connection
        """
        self.remove_pending_conn(conn_id)

    def remove_pending_conn(self, conn_id):
        return self.pending_connections.pop(conn_id, None)

    def final_conn_failure(self, conn_id):
        """ React to the information that all connection attempts failed. Call specific for this connection type
        method and then remove it from pending connections list.
        :param uuid|None conn_id: id of verified connection
        """
        conn: PendingConnection = self.pending_connections.get(conn_id)
        if conn:
            conn.final_failure()
            self.remove_pending_conn(conn_id)
        else:
            logger.debug("Connection %s is unknown", conn_id)

    def _add_pending_request(self, request_type, node,  # noqa # pylint: disable=too-many-arguments
                             prv_port, pub_port, args) -> bool:
        if not self.active:
            return False

        logger.debug('_add_pending_request(%r, %r, %r, %r, %r)',
                     request_type, node, prv_port, pub_port, args)

        sockets = [sock for sock
                   in self.get_socket_addresses(node, prv_port, pub_port)
                   if self._is_address_accessible(sock)]

        if not sockets:
            logger.debug(
                "`_add_pending_request`: no sockets found. node=%r", node)
            return False

        logger.info("Connecting to peer. node=%s, adresses=%r",
                    node_info_str(node.node_name, node.key),
                    [str(socket) for socket in sockets])

        pc = PendingConnection(request_type,
                               sockets,
                               self.conn_established_for_type[request_type],
                               self.conn_failure_for_type[request_type],
                               self.conn_final_failure_for_type[request_type],
                               args)
        self.pending_connections[pc.id] = pc
        return True

    def _is_address_accessible(self, socket_addr):
        """ Checks if an address is directly accessible. The IP address has to be public or in a private
        network that this node might have access to.
        :param socket_addr: A destination address
        :return: bool
        """
        logger.debug('_is_address_accessible(%r)', socket_addr)
        if not socket_addr:
            return False
        elif socket_addr.ipv6:
            return self.use_ipv6

        addr = socket_addr.address
        if ip_address_private(addr):
            logger.debug('_is_address_accessible(%r) PRIVATE', socket_addr)
            return self.is_address_in_network(addr)
        logger.debug('_is_address_accessible(%r) PUBLIC', socket_addr)
        return True

    def is_address_in_network(self, addr: str) -> bool:
        return self._is_address_in_network(addr, self.ipv4_networks)

    @staticmethod
    def _is_address_in_network(addr, networks):
        return any(ip_network_contains(net, mask, addr) for net, mask in networks)

    def _sync_pending(self):
        conns = [pen for pen in list(self.pending_connections.values()) if
                 pen.status in PendingConnection.connect_statuses]

        for conn in conns:
            if len(conn.socket_addresses) == 0:
                conn.status = PenConnStatus.WaitingAlt
                conn.failure()
                # TODO Implement proper way to deal with failures. Issue #2412
            else:
                conn.status = PenConnStatus.Waiting
                conn.last_try_time = time.time()
                self.network.connect(conn.connect_info)

    def get_socket_addresses(self, node_info, prv_port=None, pub_port=None):
        addresses = []

        # Primary public address
        if self._is_address_valid(node_info.pub_addr, pub_port):
            addresses.append(SocketAddress(node_info.pub_addr, pub_port))

        # Primary private address
        if node_info.prv_addr != node_info.pub_addr:
            if self._is_address_valid(node_info.prv_addr, prv_port):
                addresses.append(SocketAddress(node_info.prv_addr, prv_port))

        # The rest of private addresses
        if not isinstance(node_info.prv_addresses, list):
            return addresses

        for prv_address in node_info.prv_addresses:

            if self._is_address_valid(prv_address, prv_port):
                address = SocketAddress(prv_address, prv_port)
                if address not in addresses:
                    addresses.append(address)

            if len(addresses) >= MAX_CONNECT_SOCKET_ADDRESSES:
                break

        return addresses

    @classmethod
    def _is_address_valid(cls, address: str, port: int) -> bool:
        try:
            return port > 0 and SocketAddress.is_proper_address(address, port)
        except TypeError:
            return False

    @classmethod
    def _prepend_address(cls, addresses, address):
        try:
            index = addresses.index(address)
        except ValueError:
            addresses.insert(0, address)
        else:
            addresses.insert(0, addresses.pop(index))

    def sync_network(self, timeout=1.0):
        for session in frozenset(self.pending_sessions):
            if (time.time() - session.last_message_time) < timeout:
                continue
            # Timeouting connection
            session.dropped()

    def _set_conn_established(self):
        pass

    def _set_conn_failure(self):
        pass

    def _set_conn_final_failure(self):
        pass

    def _mark_connected(self, conn_id, addr, port):
        ad = SocketAddress(addr, port)
        pc = self.pending_connections.get(conn_id)
        if pc:
            pc.status = PenConnStatus.Connected
            if ad in pc.socket_addresses:
                pc.socket_addresses.remove(ad)
            pc.socket_addresses = [ad] + pc.socket_addresses


class PenConnStatus(object):
    """ Pending Connection Status """
    Inactive = 1
    Waiting = 2
    Connected = 3
    Failure = 4
    WaitingAlt = 5


class PendingConnection:
    """ Describe pending connections parameters for PendingConnectionsServer """
    connect_statuses = [PenConnStatus.Inactive, PenConnStatus.Failure]

    # pylint: disable-msg=too-many-arguments
    def __init__(self,
                 type_: int,
                 socket_addresses: List[SocketAddress],
                 established: Optional[Callable] = None,
                 failure: Optional[Callable] = None,
                 final_failure: Optional[Callable] = None,
                 kwargs: Kwargs = {}) -> None:
        """ Create new pending connection
        :param type_: connection type that allows to select proper reactions
        :param socket_addresses: list of socket_addresses that the node should
                                 try to connect to
        :param established: established connection callback
        :param failure: connection errback
        :param kwargs: arguments that should be passed to established or
                       failure function
        """
        self.connect_info = TCPConnectInfo(socket_addresses, established,
                                           failure, final_failure, kwargs)
        self.last_try_time = time.time()
        self.type = type_
        self.status = PenConnStatus.Inactive

    @property
    def id(self):
        return self.connect_info.id

    @property
    def socket_addresses(self):
        return self.connect_info.socket_addresses

    @socket_addresses.setter
    def socket_addresses(self, new_addresses):
        self.connect_info.socket_addresses = new_addresses

    @property
    def established(self):
        return self.connect_info.established_callback

    @property
    def failure(self):
        return self.connect_info.failure_callback

    @property
    def final_failure(self):
        return self.connect_info.final_failure_callback
