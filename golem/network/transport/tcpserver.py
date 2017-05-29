import logging
import uuid
import time

from stun import FullCone, OpenInternet
from collections import deque

from golem.core.hostaddress import ip_address_private, ip_network_contains, ipv4_networks
from server import Server
from tcpnetwork import TCPListeningInfo, TCPListenInfo, SocketAddress, TCPConnectInfo
from golem.core.variables import LISTEN_WAIT_TIME, LISTENING_REFRESH_TIME, LISTEN_PORT_TTL

logger = logging.getLogger('golem.network.transport.tcpserver')


class TCPServer(Server):
    """ Basic tcp server that can start listening on given port """

    def __init__(self, config_desc, network):
        """
        Create new server
        :param ClientConfigDescriptor config_desc: config descriptor for listening port
        :param TCPNetwork network: network that server will use
        """
        Server.__init__(self, config_desc, network)
        self.cur_port = 0  # current listening port
        self.use_ipv6 = config_desc.use_ipv6 if config_desc else False
        self.ipv4_networks = ipv4_networks()

    def change_config(self, config_desc):
        """ Change configuration descriptor. If listening port is changed, than stop listening on old port and start
        listening on a new one.
        :param ClientConfigDescriptor config_desc: new config descriptor
        """
        Server.change_config(self, config_desc)
        if self.config_desc.start_port <= self.cur_port <= self.config_desc.end_port:
            return

        if self.cur_port != 0:
            listening_info = TCPListeningInfo(self.cur_port, self._stopped_callback, self._stopped_errback)
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

        listen_info = TCPListenInfo(self.config_desc.start_port, self.config_desc.end_port,
                                    established, failure)
        self.network.listen(listen_info)

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

    supported_nat_types = [FullCone, OpenInternet]  # NAT Types that supports Nat Punching

    def __init__(self, config_desc, network):
        """ Create new server
        :param ClientConfigDescriptor config_desc: config descriptor for listening port
        :param TCPNetwork network: network that server will use
        """
        # Pending connections
        self.pending_connections = {}  # Connections that should be accomplished
        self.conn_established_for_type = {}  # Reactions for established connections of certain types
        self.conn_failure_for_type = {}  # Reactions for failed connection attempts of certain types
        self.conn_final_failure_for_type = {}  # Reactions for final connection attempts failure

        # Pending listenings
        self.pending_listenings = deque([])  # Ports that should be open for listenings
        self.listen_established_for_type = {}  # Reactions for established listenings of certain types
        self.listen_failure_for_type = {}  # Reactions for failed listenings of certain types
        self.open_listenings = {}  # Open ports
        self.listen_wait_time = LISTEN_WAIT_TIME  # How long should server wait before first try to listen
        self.last_check_listening_time = time.time()  # When was the last time when open port where checked
        self.listening_refresh_time = LISTENING_REFRESH_TIME  # How often should open ports be checked
        self.listen_port_ttl = LISTEN_PORT_TTL  # How long should port stay open

        # Set reactions
        self._set_conn_established()
        self._set_conn_failure()
        self._set_conn_final_failure()

        self._set_listen_established()
        self._set_listen_failure()

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
        conn = self.pending_connections.get(conn_id)
        if conn:
            self.conn_final_failure_for_type[conn.type](conn_id, **conn.args)
            self.remove_pending_conn(conn_id)
        else:
            logger.debug("Connection {} is unknown".format(conn_id))

    def _add_pending_request(self, req_type, task_owner, port, key_id, args):
        logger.debug('_add_pending_request(%r, %r, %r, %r, %r)', req_type, task_owner, port, key_id, args)
        sockets = [sock for sock in
                   self.get_socket_addresses(task_owner, port, key_id) if
                   self._is_address_accessible(sock)]

        pc = PendingConnection(req_type, sockets,
                               self.conn_established_for_type[req_type],
                               self.conn_failure_for_type[req_type], args)

        self.pending_connections[pc.id] = pc

    def _add_pending_listening(self, req_type, port, args):
        pl = PendingListening(req_type, port, self.listen_established_for_type[req_type],
                              self.listen_failure_for_type[req_type], args)
        pl.args["listen_id"] = pl.id
        self.pending_listenings.append(pl)

    def _is_address_accessible(self, socket_addr):
        """ Checks if an address is directly accessible. The IP address has to be public or in a private
        network that this node might have access to.
        :param socket_addr: A destination address
        :return: bool
        """
        if not socket_addr:
            return False
        elif socket_addr.ipv6:
            return self.use_ipv6

        addr = socket_addr.address
        if ip_address_private(addr):
            return self._is_address_in_network(addr, self.ipv4_networks)
        return True

    @staticmethod
    def _is_address_in_network(addr, networks):
        return any(ip_network_contains(net, mask, addr) for net, mask in networks)

    def _sync_pending(self):
        cnt_time = time.time()
        while len(self.pending_listenings) > 0:
            if cnt_time - self.pending_listenings[0].time < self.listen_wait_time:
                break
            pl = self.pending_listenings.popleft()
            listen_info = TCPListenInfo(pl.port, established_callback=pl.established, failure_callback=pl.failure)
            self.network.listen(listen_info, **pl.args)
            # self._listenOnPort(pl.port, pl.established, pl.failure, pl.args)
            self.open_listenings[pl.id] = pl  # TODO They should die after some time

        conns = [pen for pen in self.pending_connections.itervalues() if
                 pen.status in PendingConnection.connect_statuses]

        for conn in conns:
            if len(conn.socket_addresses) == 0:
                conn.status = PenConnStatus.WaitingAlt
                conn.failure(conn.id, **conn.args)
                # TODO Implement proper way to deal with failures
            else:
                conn.status = PenConnStatus.Waiting
                conn.last_try_time = time.time()
                connect_info = TCPConnectInfo(conn.socket_addresses, conn.established, conn.failure)
                self.network.connect(connect_info, conn_id=conn.id, **conn.args)

    def _remove_old_listenings(self):
        cnt_time = time.time()
        if cnt_time - self.last_check_listening_time > self.listening_refresh_time:
            self.last_check_listening_time = time.time()
            listenings_to_remove = []
            for ol_id, listening in self.open_listenings.iteritems():
                if cnt_time - listening.time > self.listen_port_ttl:
                    self.network.stop_listening(TCPListeningInfo(listening.port))
                    listenings_to_remove.append(ol_id)
            for ol_id in listenings_to_remove:
                del self.open_listenings[ol_id]

    def get_socket_addresses(self, node_info, port, key_id):
        return PendingConnectionsServer._node_info_to_socket_addresses(node_info, port)

    def _set_conn_established(self):
        pass

    def _set_conn_failure(self):
        pass

    def _set_conn_final_failure(self):
        pass

    def _set_listen_established(self):
        pass

    def _set_listen_failure(self):
        pass

    def _mark_connected(self, conn_id, addr, port):
        ad = SocketAddress(addr, port)
        pc = self.pending_connections.get(conn_id)
        if pc:
            pc.status = PenConnStatus.Connected
            if ad in pc.socket_addresses:
                pc.socket_addresses.remove(ad)
            pc.socket_addresses = [ad] + pc.socket_addresses

    @staticmethod
    def _node_info_to_socket_addresses(node_info, port):
        socket_addresses = [SocketAddress(i, port) for i in node_info.prv_addresses]
        if node_info.pub_addr is None:
            return socket_addresses
        if node_info.pub_port:
            port = node_info.pub_port
        socket_addresses.append(SocketAddress(node_info.pub_addr, port))
        return socket_addresses


class PenConnStatus(object):
    """ Pending Connection Status """
    Inactive = 1
    Waiting = 2
    Connected = 3
    Failure = 4
    WaitingAlt = 5


class PendingConnection(object):
    """ Describe pending connections parameters for PendingConnectionsServer  """
    connect_statuses = [PenConnStatus.Inactive, PenConnStatus.Failure]

    def __init__(self, type_, socket_addresses, established=None, failure=None, args=None):
        """ Create new pending connection
        :param int type_: connection type that allows to select proper reactions
        :param list socket_addresses: list of socket_addresses that the node should try to connect to
        :param func|None established: established connection callback
        :param func|None failure: connection errback
        :param dict args: arguments that should be passed to established or failure function
        """
        self.id = str(uuid.uuid4())
        self.socket_addresses = socket_addresses
        self.last_try_time = time.time()
        self.established = established
        self.failure = failure
        self.args = args
        self.type = type_
        self.status = PenConnStatus.Inactive


class PendingListening(object):
    """ Describe pending listenings parameters for PendingConnectionsServer  """
    def __init__(self, type_, port, established=None, failure=None, args=None):
        """
        :param type_: listening type that allows to select proper reactions
        :param int port: port that should be open for listening
        :param func|None established: established listening callback
        :param func|None failure: listening errback
        :param dict args: arguments that should be passed to established or failure function
        """
        self.id = str(uuid.uuid4())
        self.time = time.time()
        self.established = established
        self.failure = failure
        self.args = args
        self.port = port
        self.type = type_
        self.tries = 0
