import logging
import random
import os
import time

from golem.network.transport.network import ProtocolFactory, SessionFactory
from golem.network.transport.tcpserver import PendingConnectionsServer
from golem.network.transport.tcpnetwork import SocketAddress, TCPNetwork, FilesProtocol, DecryptFileConsumer
from golem.resource.dirmanager import DirManager
from golem.resource.resourcesmanager import DistributedResourceManager
from golem.resource.resourcesession import ResourceSession
from golem.ranking.helper.trust import Trust

logger = logging.getLogger(__name__)


class ResourceServer(PendingConnectionsServer):
    def __init__(self, config_desc, keys_auth, client, use_ipv6=False):
        self.client = client
        self.keys_auth = keys_auth
        self.resources_to_send = []
        self.resources_to_get = []
        self.res_send_it = 0
        self.peers_it = 0
        self.dir_manager = DirManager(client.datadir)
        self.resource_manager = DistributedResourceManager(self.dir_manager.get_resource_dir())
        self.use_ipv6 = use_ipv6
        network = TCPNetwork(ProtocolFactory(FilesProtocol, self, SessionFactory(ResourceSession)), use_ipv6)
        PendingConnectionsServer.__init__(self, config_desc, network)

        self.resource_peers = {}
        self.waiting_tasks = {}
        self.waiting_tasks_to_compute = {}
        self.waiting_resources = {}

        self.last_get_resource_peers_time = time.time()
        self.get_resource_peers_interval = 5.0
        self.sessions = []

        self.last_message_time_threshold = config_desc.resource_session_timeout

    def start_accepting(self):
        PendingConnectionsServer.start_accepting(self)

    def get_distributed_resource_root(self):
        return self.dir_manager.get_resource_dir()

    def get_peers(self):
        self.client.get_resource_peers()

    def add_files_to_send(self, files, task_id, num):
        res_files = {}
        for file_ in files:
            res_files[file_] = self.resource_manager.split_file(file_)
            for res in res_files[file_]:
                self.add_resource_to_send(res, num, task_id)
        return res_files

    def add_files_to_get(self, files, task_id):
        num = 0
        for file_ in files:
            if not self.resource_manager.check_resource(file_):
                num += 1
                self.add_resource_to_get(file_, task_id)

        if num > 0:
            self.waiting_tasks_to_compute[task_id] = num
        else:
            self.client.task_resource_collected(task_id)

    def add_resource_to_send(self, name, num, task_id=None):
        if task_id not in self.waiting_tasks:
            self.waiting_tasks[task_id] = 0
        self.resources_to_send.append([name, task_id, num])
        self.waiting_tasks[task_id] += 1

    def add_resource_to_get(self, name, task_id):
        self.resources_to_get.append([name, task_id])

    def new_connection(self, session):
        self.sessions.append(session)

    def add_resource_peer(self, node_name, addr, port, key_id, node_info):
        if key_id in self.resource_peers:
            if self.resource_peers[key_id]['addr'] == addr and self.resource_peers[key_id]['port'] == port and \
                    self.resource_peers[key_id]['node_name']:
                return

        self.resource_peers[key_id] = {'addr': addr, 'port': port, 'node_name': node_name, 'state': 'free',
                                       'pos_resource': 0, 'node': node_info, 'key_id': key_id}

    def set_resource_peers(self, resource_peers):
        if self.keys_auth.get_key_id() in resource_peers:
            del resource_peers[self.keys_auth.get_key_id()]

        for key_id, [addr, port, node_name, node_info] in resource_peers.iteritems():
            self.add_resource_peer(node_name, addr, port, key_id, node_info)

    def sync_network(self):
        self._sync_pending()
        if len(self.resources_to_get) + len(self.resources_to_send) > 0:
            cur_time = time.time()
            if cur_time - self.last_get_resource_peers_time > self.get_resource_peers_interval:
                self.client.get_resource_peers()
                self.last_get_resource_peers_time = time.time()
        self.send_resources()
        self.get_resources()
        self.__remove_old_sessions()

    def get_resources(self):
        if len(self.resources_to_get) == 0:
            return
        resource_peers = [peer for peer in self.resource_peers.values() if peer['state'] == 'free']
        random.shuffle(resource_peers)

        if len(self.resource_peers) == 0:
            return

        for peer in resource_peers:
            peer['state'] = 'waiting'
            self.pull_resource(self.resources_to_get[0][0], peer['addr'], peer['port'], peer['key_id'], peer['node'])

    def send_resources(self):
        if len(self.resources_to_send) == 0:
            return

        if self.res_send_it >= len(self.resources_to_send):
            self.res_send_it = len(self.resources_to_send) - 1

        resource_peers = [peer for peer in self.resource_peers.values() if peer['state'] == 'free']

        for peer in resource_peers:
            name = self.resources_to_send[self.res_send_it][0]
            num = self.resources_to_send[self.res_send_it][2]
            peer['state'] = 'waiting'
            self.push_resource(name, peer['addr'], peer['port'], peer['key_id'], peer['node'], num)
            self.res_send_it = (self.res_send_it + 1) % len(self.resources_to_send)

    def pull_resource(self, resource, addr, port, key_id, node_info):
        args = {"resource": resource, "resource_address": addr, "resource_port": port, "key_id": key_id}
        self._add_pending_request(ResourceConnTypes.Pull, node_info, port, key_id, args)

    def pull_answer(self, resource, has_resource, session):
        if not has_resource or resource not in [res[0] for res in self.resources_to_get]:
            self.__free_peer(session.address, session.port)
            session.dropped()
        else:
            if resource not in self.waiting_resources:
                self.waiting_resources[resource] = []
            for res in self.resources_to_get:
                if res[0] == resource:
                    self.waiting_resources[resource].append(res[1])
            for task_id in self.waiting_resources[resource]:
                self.resources_to_get.remove([resource, task_id])
            session.file_name = resource
            session.conn.stream_mode = True
            session.conn.confirmation = False
            session.send_want_resource(resource)
            session.conn.consumer = DecryptFileConsumer([self.prepare_resource(session.file_name)], "", session, {})

            if session not in self.sessions:
                self.sessions.append(session)

    def push_resource(self, resource, addr, port, key_id, node_info, copies):
        args = {"resource": resource, "copies": copies, "resource_address": addr, "resource_port": port,
                "key_id": key_id}
        self._add_pending_request(ResourceConnTypes.Push, node_info, port, key_id, args)

    def check_resource(self, resource):
        return self.resource_manager.check_resource(resource)

    def prepare_resource(self, resource):
        return self.resource_manager.get_resource_path(resource)

    def resource_downloaded(self, resource, address, port):
        key_id = self.__free_peer(address, port)
        if not self.resource_manager.check_resource(resource):
            logger.error("Wrong resource downloaded\n")
            if key_id is not None:
                Trust.RESOURCE.decrease(key_id)
            return
        if key_id is not None:
            # We update ranking after 100 chunks
            self.resource_peers[key_id]['pos_resource'] += 1
            if (self.resource_peers[key_id]['pos_resource'] % 50) == 0:
                Trust.RESOURCE.increase(key_id, 50)
        for task_id in self.waiting_resources[resource]:
            self.waiting_tasks_to_compute[task_id] -= 1
            if self.waiting_tasks_to_compute[task_id] == 0:
                self.client.task_resource_collected(task_id)
                del self.waiting_tasks_to_compute[task_id]
        del self.waiting_resources[resource]

    def has_resource(self, resource, addr, port):
        remove_res = False
        for res in self.resources_to_send:

            if resource == res[0]:
                res[2] -= 1
                if res[2] == 0:
                    remove_res = True
                    task_id = res[1]
                    self.waiting_tasks[task_id] -= 1
                    if self.waiting_tasks[task_id] == 0:
                        del self.waiting_tasks[task_id]
                        if task_id is not None:
                            self.client.task_resource_send(task_id)
                    break

        if remove_res:
            self.resources_to_send.remove([resource, task_id, 0])

        self.__free_peer(addr, port)

    def unpack_delta(self, dest_dir, delta, task_id):
        if not os.path.isdir(dest_dir):
            os.mkdir(dest_dir)
        for dir_header in delta.sub_dir_headers:
            self.unpack_delta(os.path.join(dest_dir, dir_header.dir_name), dir_header, task_id)

        for files_data in delta.files_data:
            self.resource_manager.connect_file(files_data[2], os.path.join(dest_dir, files_data[0]))

    def remove_session(self, session):
        if session in self.sessions:
            self.__free_peer(session.address, session.port)
            self.sessions.remove(session)

    def get_key_id(self):
        return self.keys_auth.get_key_id()

    def get_socket_addresses(self, node_info, port, key_id):
        if self.client.get_suggested_conn_reverse(key_id):
            return []
        addr = self.client.get_suggested_addr(key_id)
        socket_addresses = PendingConnectionsServer.get_socket_addresses(self, node_info, port, key_id)
        if addr:
            socket_addresses = [SocketAddress(addr, port)] + socket_addresses
        return socket_addresses

    def encrypt(self, message, public_key):
        if public_key == 0:
            return message
        return self.keys_auth.encrypt(message, public_key)

    def decrypt(self, message):
        return self.keys_auth.decrypt(message)

    def sign(self, data):
        return self.keys_auth.sign(data)

    def verify_sig(self, sig, data, public_key):
        return self.keys_auth.verify(sig, data, public_key)

    def change_config(self, config_desc):
        self.last_message_time_threshold = config_desc.resource_session_timeout

    def _set_conn_established(self):
        self.conn_established_for_type.update({
            ResourceConnTypes.Pull: self.__connection_pull_resource_established,
            ResourceConnTypes.Push: self.__connection_push_resource_established,
            ResourceConnTypes.Resource: self.__connection_for_resource_established
        })

    def _set_conn_failure(self):
        self.conn_failure_for_type.update({
            ResourceConnTypes.Pull: self.__connection_pull_resource_failure,
            ResourceConnTypes.Push: self.__connection_push_resource_failure,
            ResourceConnTypes.Resource: self.__connection_for_resource_failure
        })

    def _set_conn_final_failure(self):
        self.conn_final_failure_for_type.update({
            ResourceConnTypes.Pull: self.__connection_final_failure,
            ResourceConnTypes.Push: self.__connection_final_failure,
            ResourceConnTypes.Resource: self.__connection_final_failure
        })

    def __free_peer(self, addr, port):
        for key_id, peer in self.resource_peers.iteritems():
            if peer['addr'] == addr and peer['port'] == port:
                self.resource_peers[key_id]['state'] = 'free'
                return key_id

    def __connection_push_resource_established(self, session, conn_id, resource, copies, resource_address,
                                               resource_port, key_id):
        session.key_id = key_id
        session.conn_id = conn_id
        session.send_hello()
        session.send_push_resource(resource, copies)
        self.sessions.append(session)

    def __connection_push_resource_failure(self, conn_id, resource, copies, resource_address, resource_port, key_id):
        self.__remove_client(resource_address, resource_port)
        logger.error("Connection to resource server failed")

    def __connection_pull_resource_established(self, session, conn_id, resource, resource_address, resource_port,
                                               key_id):
        session.key_id = key_id
        session.conn_id = conn_id
        session.send_hello()
        session.send_pull_resource(resource)
        self.sessions.append(session)

    def __connection_pull_resource_failure(self, conn_id, resource, resource_address, resource_port, key_id):
        self.__remove_client(resource_address, resource_port)
        logger.error("Connection to resource server failed")

    def __connection_for_resource_established(self, session, conn_id, resource, resource_address, resource_port,
                                              key_id):
        session.key_id = key_id
        session.conn_id = conn_id
        session.send_hello()
        session.send_want_resource(resource)
        self.sessions.append(session)

    def __connection_for_resource_failure(self, conn_id, resource, resource_address, resource_port):
        self.__remove_client(resource_address, resource_port)
        logger.error("Connection to resource server failed")

    def __connection_final_failure(self, conn_id, resource, resource_address, resource_port):
        pass

    def __remove_client(self, addr, port):
        bad_client = None
        for key_id, peer in self.resource_peers.iteritems():
            if peer['addr'] == addr and peer['port'] == port:
                bad_client = key_id
                break

        if bad_client is not None:
            del self.resource_peers[bad_client]

    def __remove_old_sessions(self):
        cur_time = time.time()
        sessions_to_remove = []
        for session in self.sessions:
            if cur_time - session.last_message_time > self.last_message_time_threshold:
                sessions_to_remove.append(session)
        for session in sessions_to_remove:
            self.remove_session(session)

    def _listening_established(self, port, **kwargs):
        self.cur_port = port
        logger.info("Port {} opened - listening.".format(self.cur_port))
        self.client.set_resource_port(self.cur_port)


class ResourceConnTypes(object):
    """ Resource Connection Types that allows to choose right reaction """
    Pull = 1
    Push = 2
    Resource = 3
