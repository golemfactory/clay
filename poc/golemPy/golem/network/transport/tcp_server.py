import logging
import uuid
import time

from stun import FullCone, OpenInternet
from collections import deque

from server import Server
from tcp_network import TCPListeningInfo, TCPListenInfo, TCPAddress, TCPConnectInfo

logger = logging.getLogger(__name__)


class TCPServer(Server):
    def __init__(self, config_desc, network):
        Server.__init__(self, config_desc, network)
        self.cur_port = 0

    def change_config(self, config_desc):
        Server.change_config(self, config_desc)
        if self.cur_port != 0:
            listening_info = TCPListeningInfo(self.cur_port, self._stopped_callback, self._stopped_errback)
            self.network.stop_listening(listening_info)

        self.start_accepting()

    def start_accepting(self):
        listen_info = TCPListenInfo(self.config_desc.startPort, self.config_desc.endPort,
                                    self._listening_established, self._listening_failure)
        self.network.listen(listen_info)

    def _stopped_callback(self):
        logger.debug("Stopped listening on previous port")

    def _stopped_errback(self):
        logger.debug("Failed to stop listening on previous port")

    def _listening_established(self, port):
        self.cur_port = port
        logger.info("Port {} opened - listening.".format(self.cur_port))

    def _listening_failure(self):
        logger.error("Listening on ports {} to {} failure.").format(self.config_desc.startPort,
                                                                    self.config_desc.endPort)


class PendingConnectionsServer(TCPServer):
    supported_nat_types = [FullCone, OpenInternet]

    def __init__(self, config_desc, network):
        self.pending_connections = {}
        self.conn_established_for_type = {}
        self.conn_failure_for_type = {}
        self.conn_final_failure_for_type = {}
        self._set_conn_established()
        self._set_conn_failure()
        self._set_conn_final_failure()

        self.pending_listenings = deque([])
        self.open_listenings = {}
        self.listen_wait_time = 1
        self.listenEstablishedForType = {}
        self.listenFailureForType = {}
        self._set_listen_established()
        self._set_listen_failure()
        self.last_check_listening_time = time.time()
        self.listening_refresh_time = 120
        self.listen_port_ttl = 3600

        TCPServer.__init__(self, config_desc, network)

    def change_config(self, config_desc):
        TCPServer.change_config(self, config_desc)

    def start_accepting(self):
        TCPServer.start_accepting(self)

    def verified_conn(self, conn_id):
        if conn_id in self.pending_connections:
            del self.pending_connections[conn_id]
        else:
            logger.error("Connection {} is unknown".format(conn_id))

    def final_conn_failure(self, conn_id):
        conn = self.pending_connections.get(conn_id)
        if conn:
            self.conn_final_failure_for_type[conn.type](conn_id, *conn.args)
            del self.pending_connections[conn_id]
        else:
            logger.error("Connection {} is unknown".format(conn_id))

    def _add_pending_request(self, type_, task_owner, port, key_id, args):
        tcp_addresses = self._get_tcp_addresses(task_owner, port, key_id)
        pc = PendingConnection(type_, tcp_addresses, self.conn_established_for_type[type_],
                               self.conn_failure_for_type[type_], args)
        self.pending_connections[pc.id] = pc

    def _add_pending_listening(self, type_, port, args):
        pl = PendingListening(type_, port, self.listenEstablishedForType[type_],
                              self.listenFailureForType[type_], args)
        pl.args["listenId"] = pl.id
        self.pending_listenings.append(pl)

    def _sync_pending(self):
        cnt_time = time.time()
        while len(self.pending_listenings) > 0:
            if cnt_time - self.pending_listenings[0].time < self.listen_wait_time:
                break
            pl = self.pending_listenings.popleft()
            listen_info = TCPListenInfo(pl.port, established_callback=pl.established, failure_callback=pl.failure)
            self.network.listen(listen_info, **pl.args)
            # self._listenOnPort(pl.port, pl.established, pl.failure, pl.args)
            self.open_listenings[pl.id] = pl  # TODO Powinny umierac jesli zbyt dlugo sa aktywne

        conns = [pen for pen in self.pending_connections.itervalues() if
                 pen.status in PendingConnection.connect_statuses]
        # TODO Zmiany dla innych statusow
        for conn in conns:
            if len(conn.tcp_addresses) == 0:
                conn.status = PenConnStatus.WaitingAlt
                conn.failure(conn.id, **conn.args)
                # TODO Dalsze dzialanie w razie niepowodzenia
            else:
                conn.status = PenConnStatus.Waiting
                conn.last_try_time = time.time()

                connect_info = TCPConnectInfo(conn.tcp_addresses, conn.established, conn.failure)
                self.network.connect(connect_info, conn_id=conn.id, **conn.args)

    def _remove_old_listenings(self):
        cnt_time = time.time()
        if cnt_time - self.last_check_listening_time > self.listening_refresh_time:
            self.last_check_listening_time = time.time()
            listenings_to_remove = []
            for ol_id, listening in self.open_listenings.iteritems():
                if cnt_time - listening.time > self.listen_port_ttl:
                    if listening.listenPort:
                        listening.listenPort.stopListening()
                    listenings_to_remove.append(ol_id)
            for ol_id in listenings_to_remove:
                del self.open_listenings[ol_id]

    def _get_tcp_addresses(self, node_info, port, key_id):
        return PendingConnectionsServer.__node_info_to_tcp_addresses(node_info, port)

    @staticmethod
    def __node_info_to_tcp_addresses(node_info, port):
        tcp_addresses = [TCPAddress(i, port) for i in node_info.prvAddresses]
        if node_info.pubPort:
            tcp_addresses.append(TCPAddress(node_info.pubAddr, node_info.pubPort))
        else:
            tcp_addresses.append(TCPAddress(node_info.pubAddr, port))
        return tcp_addresses

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
        ad = TCPAddress(addr, port)
        pc = self.pending_connections.get(conn_id)
        if pc is not None:
            pc.status = PenConnStatus.Connected
            try:
                idx = pc.tcp_addresses.index(ad)
                pc.tcp_addresses = pc.tcp_addresses[idx + 1:]
            except ValueError:
                logger.warning("{}:{} not in connection tcp_addresses".format(addr, port))


class PenConnStatus(object):
    Inactive = 1
    Waiting = 2
    Connected = 3
    Failure = 4
    WaitingAlt = 5


class PendingConnection(object):
    connect_statuses = [PenConnStatus.Inactive, PenConnStatus.Failure]

    def __init__(self, type_=None, tcp_addresses=None, established=None, failure=None, args=None):
        self.id = uuid.uuid4()
        self.tcp_addresses = tcp_addresses
        self.last_try_time = time.time()
        self.established = established
        self.failure = failure
        self.args = args
        self.type = type_
        self.status = PenConnStatus.Inactive


class PendingListening(object):
    def __init__(self, type_=None, port=None, established=None, failure=None, args=None):
        self.id = uuid.uuid4()
        self.time = time.time()
        self.established = established
        self.failure = failure
        self.args = args
        self.port = port
        self.type = type_
        self.tries = 0
        self.listening_port = None
