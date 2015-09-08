import logging
import random
import os
import time

from golem.network.transport.network import ProtocolFactory, SessionFactory
from golem.network.transport.tcp_server import TCPServer
from golem.network.transport.tcp_network import TCPConnectInfo, TCPAddress, TCPListenInfo, TCPNetwork, FilesProtocol
from golem.resource.DirManager import DirManager
from golem.resource.ResourcesManager import DistributedResourceManager
from golem.resource.resource_session import ResourceSession
from golem.ranking.Ranking import RankingStats


logger = logging.getLogger(__name__)


class ResourceServer(TCPServer):

    def __init__(self, config_desc, keys_auth, client, use_ipv6=False):
        self.client = client
        self.keys_auth = keys_auth
        self.resourcesToSend = []
        self.resourcesToGet = []
        self.resSendIt = 0
        self.peersIt = 0
        self.dir_manager = DirManager(config_desc.root_path, config_desc.client_uid)
        self.resource_manager = DistributedResourceManager(self.dir_manager.getResourceDir())
        self.use_ipv6 = use_ipv6
        network = TCPNetwork(ProtocolFactory(FilesProtocol, self, SessionFactory(ResourceSession)),  use_ipv6)
        TCPServer.__init__(self, config_desc, network)

        self.resource_peers = {}
        self.waitingTasks = {}
        self.waitingTasksToCompute = {}
        self.waitingResources = {}

        self.lastGetResourcePeersTime  = time.time()
        self.getResourcePeersInterval = 5.0
        self.sessions = []

        self.last_message_time_threshold = config_desc.resource_session_timeout

    def start_accepting(self):
        TCPServer.start_accepting(self)

    def change_resource_dir(self, config_desc):
        if self.dir_manager.root_path == config_desc.root_path:
            return
        self.dir_manager.root_path = config_desc.root_path
        self.dir_manager.node_id = config_desc.client_uid
        self.resource_manager.change_resource_dir(self.dir_manager.getResourceDir())

    def get_distributed_resource_root(self):
        return self.dir_manager.getResourceDir()

    def get_peers(self):
        self.client.get_resource_peers()

    def add_files_to_send(self, files, task_id, num):
        res_files = {}
        for file_ in files:
            res_files[file_] = self.resource_manager.splitFile(file_)
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
            self.waitingTasksToCompute[task_id] = num
        else:
            self.client.taskResourcesCollected(task_id)

    def add_resource_to_send(self, name, num, task_id = None):
        if task_id not in self.waitingTasks:
            self.waitingTasks[task_id] = 0
        self.resourcesToSend.append([name, task_id, num])
        self.waitingTasks[task_id] += 1

    def add_resource_to_get(self, name, task_id):
        self.resourcesToGet.append([name, task_id])

    def new_connection(self, session):
        self.sessions.append(session)

    new_connection = new_connection

    def add_resource_peer(self, client_id, addr, port, key_id, node_info):
        if client_id in self.resource_peers:
            if self.resource_peers[client_id]['addr'] == addr and self.resource_peers[client_id]['port'] == port and self.resource_peers[client_id]['key_id']:
                return

        self.resource_peers[client_id] = { 'addr': addr, 'port': port, 'key_id': key_id, 'state': 'free', 'posResource': 0,
                                           'node': node_info}

    def set_resource_peers(self, resource_peers):
        if self.config_desc.client_uid in resource_peers:
            del resource_peers[self.config_desc.client_uid]

        for client_id, [addr, port, key_id, node_info] in resource_peers.iteritems():
            self.add_resource_peer(client_id, addr, port, key_id, node_info)

    def sync_network(self):
        if len(self.resourcesToGet) + len(self.resourcesToSend) > 0:
            cur_time = time.time()
            if cur_time - self.lastGetResourcePeersTime > self.getResourcePeersInterval:
                self.client.get_resource_peers()
                self.lastGetResourcePeersTime = time.time()
        self.send_resources()
        self.get_resources()
        self.__remove_old_sessions()

    def get_resources(self):
        if len (self.resourcesToGet) == 0:
            return
        resource_peers = [peer for peer in self.resource_peers.values() if peer['state'] == 'free']
        random.shuffle(resource_peers)

        if len (self.resource_peers) == 0:
            return

        for peer in resource_peers:
            peer['state'] = 'waiting'
            self.pull_resource(self.resourcesToGet[0][0], peer['addr'], peer['port'], peer['key_id'], peer['node'])

    def send_resources(self):
        if len(self.resourcesToSend) == 0:
            return

        if self.resSendIt >= len(self.resourcesToSend):
            self.resSendIt = len(self.resourcesToSend) - 1

        resource_peers = [peer for peer in self.resource_peers.values() if peer['state'] == 'free']

        for peer in resource_peers:
            name = self.resourcesToSend[self.resSendIt][0]
            num = self.resourcesToSend[self.resSendIt][2]
            peer['state'] = 'waiting'
            self.push_resource(name , peer['addr'], peer['port'] , peer['key_id'], peer['node'], num)
            self.resSendIt = (self.resSendIt + 1) % len(self.resourcesToSend)

    def pull_resource(self, resource, addr, port, key_id, node_info):
        tcp_addresses = self._node_info_to_tcp_addresses(node_info, port)
        addr = self.client.getSuggestedAddr(key_id)
        if addr:
            tcp_addresses = [TCPAddress(addr, port)] + tcp_addresses
        connect_info = TCPConnectInfo(tcp_addresses, self.__connection_pull_resource_established,
                                      self.__connection_pull_resource_failure)
        self.network.connect(connect_info, resource=resource, resource_address=addr, resource_port=port, key_id=key_id)

    def pull_answer(self, resource, has_resource, session):
        if not has_resource or resource not in [res[0] for res in self.resourcesToGet]:
            self.__free_peer(session.address, session.port)
            session.dropped()
        else:
            if resource not in self.waitingResources:
                self.waitingResources[resource] = []
            for res in self.resourcesToGet:
                if res[0] == resource:
                    self.waitingResources[resource].append(res[1])
            for task_id in self.waitingResources[resource]:
                    self.resourcesToGet.remove([resource, task_id])
            session.fileName = resource
            session.conn.file_mode = True
            session.conn.confirmation = False
            session.send_want_resource(resource)
            if session not in self.sessions:
                self.sessions.append(session)

    def push_resource(self, resource, addr, port, key_id, node_info, copies):

        tcp_addresses = self._node_info_to_tcp_addresses(node_info, port)
        addr = self.client.getSuggestedAddr(key_id)
        if addr:
            tcp_addresses = [TCPAddress(addr, port)] + tcp_addresses
        connect_info = TCPConnectInfo(tcp_addresses, self.__connection_push_resource_established,
                                      self.__connection_push_resource_failure)
        self.network.connect(connect_info, resource=resource, copies=copies, resource_address=addr, resource_port=port,
                             key_id=key_id)

    def check_resource(self, resource):
        return self.resource_manager.check_resource(resource)

    def prepare_resource(self, resource):
        return self.resource_manager.getResourcePath(resource)

    def resource_downloaded(self, resource, address, port):
        client_id = self.__free_peer(address, port)
        if not self.resource_manager.check_resource(resource):
            logger.error("Wrong resource downloaded\n")
            if client_id is not None:
                self.client.decreaseTrust(client_id, RankingStats.resource)
            return
        if client_id is not None:
            # Uaktualniamy ranking co 100 zasobow, zeby specjalnie nie zasmiecac sieci
            self.resource_peers[client_id]['posResource'] += 1
            if (self.resource_peers[client_id]['posResource'] % 50) == 0:
                self.client.increaseTrust(client_id, RankingStats.resource, 50)
        for task_id in self.waitingResources[resource]:
            self.waitingTasksToCompute[task_id] -= 1
            if self.waitingTasksToCompute[task_id] == 0:
                self.client.taskResourcesCollected(task_id)
                del self.waitingTasksToCompute[task_id]
        del self.waitingResources[resource]

    def has_resource(self, resource, addr, port):
        remove_res = False
        for res in self.resourcesToSend:

            if resource == res[0]:
                res[2] -= 1
                if res[2] == 0:
                    remove_res = True
                    task_id = res[1]
                    self.waitingTasks[task_id] -= 1
                    if self.waitingTasks[task_id] == 0:
                        del self.waitingTasks[task_id]
                        if task_id is not None:
                            self.client.taskResourcesSend(task_id)
                    break

        if remove_res:
            self.resourcesToSend.remove([resource, task_id, 0])

        self.__free_peer(addr, port)

    def unpack_delta(self, dest_dir, delta, task_id):
        if not os.path.isdir(dest_dir):
            os.mkdir(dest_dir)
        for dirHeader in delta.subDirHeaders:
            self.unpack_delta(os.path.join(dest_dir, dirHeader.dirName), dirHeader, task_id)

        for filesData in delta.filesData:
            self.resource_manager.connectFile(filesData[2], os.path.join(dest_dir, filesData[0]))

    def remove_session(self, session):
        if session in self.sessions:
            self.__free_peer(session.address, session.port)
            self.sessions.remove(session)

    def get_key_id(self):
        return self.keys_auth.get_key_id()

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

    @staticmethod
    def _node_info_to_tcp_addresses(node_info, port):
        tcp_addresses = [TCPAddress(i, port) for i in node_info.prvAddresses]
        if node_info.pubPort:
            tcp_addresses.append(TCPAddress(node_info.pubAddr, node_info.pubPort))
        else:
            tcp_addresses.append(TCPAddress(node_info.pubAddr, port))
        return tcp_addresses

    def __free_peer(self, addr, port):
        for client_id, value in self.resource_peers.iteritems():
            if value['addr'] == addr and value['port'] == port:
                self.resource_peers[client_id]['state'] = 'free'
                return client_id

    def __connection_push_resource_established(self, session, resource, copies, resource_address, resource_port, key_id):
        session.key_id = key_id
        session.send_hello()
        session.send_push_resource(resource, copies)
        self.sessions.append(session)

    def __connection_push_resource_failure(self, resource, copies, resource_address, resource_port, key_id):
        self.__remove_client(resource_address, resource_port)
        logger.error("Connection to resource server failed")

    def __connection_pull_resource_established(self, session, resource, resource_address, resource_port, key_id):
        session.key_id = key_id
        session.send_hello()
        session.send_pull_resource(resource)
        self.sessions.append(session)

    def __connection_pull_resource_failure(self, resource, resource_address, resource_port, key_id):
        self.__remove_client(resource_address, resource_port)
        logger.error("Connection to resource server failed")

    def __connection_for_resource_established(self, session, resource, resource_address, resource_port, key_id):
        session.key_id = key_id
        session.send_hello()
        session.send_want_resource(resource)
        self.sessions.append(session)

    def __connection_for_resource_failure(self, resource, resource_address, resource_port):
        self.__remove_client(resource_address, resource_port)
        logger.error("Connection to resource server failed")

    def __remove_client(self, addr, port):
        bad_client = None
        for client_id, peer in self.resource_peers.iteritems():
            if peer['addr'] == addr and peer['port'] == port:
                bad_client = client_id
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
        TCPServer._listening_established(self, port, **kwargs)
        self.client.setResourcePort(self.cur_port)

