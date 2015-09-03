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

##########################################################
class ResourceServer(TCPServer):
    ############################
    def __init__(self, config_desc, keys_auth, client, useIp6=False):
        self.client = client
        self.keys_auth = keys_auth
        self.resourcesToSend = []
        self.resourcesToGet = []
        self.resSendIt = 0
        self.peersIt = 0
        self.dirManager = DirManager(config_desc.rootPath, config_desc.clientUid)
        self.resourceManager = DistributedResourceManager(self.dirManager.getResourceDir())
        self.useIp6=useIp6
        network = TCPNetwork(ProtocolFactory(FilesProtocol, self, SessionFactory(ResourceSession)),  useIp6)
        TCPServer.__init__(self, config_desc, network)

        self.resource_peers = {}
        self.waitingTasks = {}
        self.waitingTasksToCompute = {}
        self.waitingResources = {}

        self.lastGetResourcePeersTime  = time.time()
        self.getResourcePeersInterval = 5.0
        self.sessions = []

        self.last_message_time_threshold = config_desc.resourceSessionTimeout

    ############################
    def start_accepting(self):
        TCPServer.start_accepting(self)

    ############################
    def changeResourceDir(self, config_desc):
        if self.dirManager.rootPath == config_desc.rootPath:
            return
        self.dirManager.rootPath = config_desc.rootPath
        self.dirManager.nodeId = config_desc.clientUid
        self.resourceManager.changeResourceDir(self.dirManager.getResourceDir())

    ############################
    def getDistributedResourceRoot(self):
        return self.dirManager.getResourceDir()

    ############################
    def get_peers(self):
        self.client.get_resource_peers()

    ############################
    def addFilesToSend(self, files, taskId, num):
        resFiles = {}
        for file_ in files:
            resFiles[file_] = self.resourceManager.splitFile(file_)
            for res in resFiles[file_]:
                self.addResourceToSend(res, num, taskId)
        return resFiles

    ############################
    def addFilesToGet(self, files, taskId):
        num = 0
        for file_ in files:
            if not self.resourceManager.checkResource(file_):
                num += 1
                self.addResourceToGet(file_, taskId)

        if (num > 0):
            self.waitingTasksToCompute[taskId] = num
        else:
            self.client.taskResourcesCollected(taskId)

    ############################
    def addResourceToSend(self, name, num, taskId = None):
        if taskId not in self.waitingTasks:
            self.waitingTasks[taskId] = 0
        self.resourcesToSend.append([name, taskId, num])
        self.waitingTasks[taskId] += 1

    ############################
    def addResourceToGet(self, name, taskId):
        self.resourcesToGet.append([name, taskId])

    ############################
    def newConnection(self, session):
        self.sessions.append(session)

    new_connection = newConnection

    ############################
    def addResourcePeer(self, client_id, addr, port, keyId, node_info):
        if client_id in self.resource_peers:
            if self.resource_peers[client_id]['addr'] == addr and self.resource_peers[client_id]['port'] == port and self.resource_peers[client_id]['keyId']:
                return

        self.resource_peers[client_id] = { 'addr': addr, 'port': port, 'keyId': keyId, 'state': 'free', 'posResource': 0,
                                           'node': node_info}

    ############################
    def set_resource_peers(self, resource_peers):
        if self.config_desc.clientUid in resource_peers:
            del resource_peers[self.config_desc.clientUid]

        for client_id, [addr, port, keyId, node_info] in resource_peers.iteritems():
            self.addResourcePeer(client_id, addr, port, keyId, node_info)

    ############################
    def sync_network(self):
        if len(self.resourcesToGet) + len(self.resourcesToSend) > 0:
            cur_time = time.time()
            if cur_time - self.lastGetResourcePeersTime > self.getResourcePeersInterval:
                self.client.get_resource_peers()
                self.lastGetResourcePeersTime = time.time()
        self.sendResources()
        self.getResources()
        self.__removeOldSessions()

    ############################
    def getResources(self):
        if len (self.resourcesToGet) == 0:
            return
        resource_peers = [peer for peer in self.resource_peers.values() if peer['state'] == 'free']
        random.shuffle(resource_peers)

        if len (self.resource_peers) == 0:
            return

        for peer in resource_peers:
            peer['state'] = 'waiting'
            self.pullResource(self.resourcesToGet[0][0], peer['addr'], peer['port'], peer['keyId'], peer['node'])


    ############################
    def sendResources(self):
        if len(self.resourcesToSend) == 0:
            return

        if self.resSendIt >= len(self.resourcesToSend):
            self.resSendIt = len(self.resourcesToSend) - 1

        resource_peers = [peer for peer in self.resource_peers.values() if peer['state'] == 'free']

        for peer in resource_peers:
            name = self.resourcesToSend[self.resSendIt][0]
            num = self.resourcesToSend[self.resSendIt][2]
            peer['state'] = 'waiting'
            self.pushResource(name , peer['addr'], peer['port'] , peer['keyId'], peer['node'], num)
            self.resSendIt = (self.resSendIt + 1) % len(self.resourcesToSend)

    ############################
    def pullResource(self, resource, addr, port, keyId, node_info):
        tcp_addresses = self.__node_info_to_tcp_addresses(node_info, port)
        addr = self.client.getSuggestedAddr(keyId)
        if addr:
            tcp_addresses = [TCPAddress(addr, port)] + tcp_addresses
        connect_info = TCPConnectInfo(tcp_addresses, self.__connectionPullResourceEstablished,
                                      self.__connectionPullResourceFailure)
        self.network.connect(connect_info, resource=resource, resource_address=addr, resource_port=port, keyId=keyId)


    ############################
    def pullAnswer(self, resource, hasResource, session):
        if not hasResource or resource not in [res[0] for res in self.resourcesToGet]:
            self.__freePeer(session.address, session.port)
            session.dropped()
        else:
            if resource not in self.waitingResources:
                self.waitingResources[resource] = []
            for res in self.resourcesToGet:
                if res[0] == resource:
                    self.waitingResources[resource].append(res[1])
            for taskId in self.waitingResources[resource]:
                    self.resourcesToGet.remove([resource, taskId])
            session.fileName = resource
            session.conn.file_mode = True
            session.conn.confirmation = False
            session.send_want_resource(resource)
            if session not in self.sessions:
                self.sessions.append(session)

    ############################
    def pushResource(self, resource, addr, port, keyId, node_info, copies):

        tcp_addresses = self.__node_info_to_tcp_addresses(node_info, port)
        addr = self.client.getSuggestedAddr(keyId)
        if addr:
            tcp_addresses = [TCPAddress(addr, port)] + tcp_addresses
        connect_info = TCPConnectInfo(tcp_addresses, self.__connectionPushResourceEstablished,
                                      self.__connectionPushResourceFailure)
        self.network.connect(connect_info, resource=resource, copies=copies, resource_address=addr, resource_port=port,
                             keyId=keyId)

    ############################
    def checkResource(self, resource):
        return self.resourceManager.checkResource(resource)

    ############################
    def prepareResource(self, resource):
        return self.resourceManager.getResourcePath(resource)

    ############################
    def resourceDownloaded(self, resource, address, port):
        client_id = self.__freePeer(address, port)
        if not self.resourceManager.checkResource(resource):
            logger.error("Wrong resource downloaded\n")
            if client_id is not None:
                self.client.decreaseTrust(client_id, RankingStats.resource)
            return
        if client_id is not None:
            # Uaktualniamy ranking co 100 zasobow, zeby specjalnie nie zasmiecac sieci
            self.resource_peers[client_id]['posResource'] += 1
            if (self.resource_peers[client_id]['posResource'] % 50) == 0:
                self.client.increaseTrust(client_id, RankingStats.resource, 50)
        for taskId in self.waitingResources[resource]:
            self.waitingTasksToCompute[taskId] -= 1
            if self.waitingTasksToCompute[taskId] == 0:
                self.client.taskResourcesCollected(taskId)
                del self.waitingTasksToCompute[taskId]
        del self.waitingResources[resource]

    ############################
    def hasResource(self, resource, addr, port):
        removeRes = False
        for res in self.resourcesToSend:

            if resource == res[0]:
                res[2] -= 1
                if res[2] == 0:
                    removeRes = True
                    taskId = res[1]
                    self.waitingTasks[taskId] -= 1
                    if self.waitingTasks[taskId] == 0:
                        del self.waitingTasks[taskId]
                        if taskId is not None:
                            self.client.taskResourcesSend(taskId)
                    break

        if removeRes:
            self.resourcesToSend.remove([resource, taskId, 0])

        self.__freePeer(addr, port)

    ############################
    def unpackDelta(self, destDir, delta, taskId):
        if not os.path.isdir(destDir):
            os.mkdir(destDir)
        for dirHeader in delta.subDirHeaders:
            self.unpackDelta(os.path.join(destDir, dirHeader.dirName), dirHeader, taskId)

        for filesData in delta.filesData:
            self.resourceManager.connectFile(filesData[2], os.path.join(destDir, filesData[0]))

    ############################
    def removeSession(self, session):
        if session in self.sessions:
            self.__freePeer(session.address, session.port)
            self.sessions.remove(session)

    #############################
    def get_key_id(self):
        return self.keys_auth.get_key_id()

    #############################
    def encrypt(self, message, publicKey):
        if publicKey == 0:
            return message
        return self.keys_auth.encrypt(message, publicKey)

    #############################
    def decrypt(self, message):
        return self.keys_auth.decrypt(message)

    #############################
    def sign(self, data):
        return self.keys_auth.sign(data)

    #############################
    def verify_sig(self, sig, data, publicKey):
        return self.keys_auth.verify(sig, data, publicKey)


    ############################
    def change_config(self, config_desc):
        self.last_message_time_threshold = config_desc.resourceSessionTimeout

    @staticmethod
    def __node_info_to_tcp_addresses(node_info, port):
        tcp_addresses = [TCPAddress(i, port) for i in node_info.prvAddresses]
        if node_info.pubPort:
            tcp_addresses.append(TCPAddress(node_info.pubAddr, node_info.pubPort))
        else:
            tcp_addresses.append(TCPAddress(node_info.pubAddr, port))
        return tcp_addresses

    ############################
    def __freePeer(self, addr, port):
        for client_id, value in self.resource_peers.iteritems():
            if value['addr'] == addr and value['port'] == port:
                self.resource_peers[client_id]['state'] = 'free'
                return client_id


    ############################
    def __connectionPushResourceEstablished(self, session, resource, copies, resource_address, resource_port, keyId):
        session.key_id = keyId
        session.send_hello()
        session.send_push_resource(resource, copies)
        self.sessions.append(session)

    ############################
    def __connectionPushResourceFailure(self, resource, copies, resource_address, resource_port, keyId):
        self.__removeClient(resource_address, resource_port)
        logger.error("Connection to resource server failed")

    ############################
    def __connectionPullResourceEstablished(self, session, resource, resource_address, resource_port, keyId):
        session.key_id = keyId
        session.send_hello()
        session.send_pull_resource(resource)
        self.sessions.append(session)

    ############################
    def __connectionPullResourceFailure(self, resource, resource_address, resource_port, keyId):
        self.__removeClient(resource_address, resource_port)
        logger.error("Connection to resource server failed")

    ############################
    def __connectionForResourceEstablished(self, session, resource, resource_address, resource_port, keyId):
        session.key_id = keyId
        session.send_hello()
        session.send_want_resource(resource)
        self.sessions.append(session)

    ############################
    def __connectionForResourceFailure(self, resource, resource_address, resource_port):
        self.__removeClient(resource_address, resource_port)
        logger.error("Connection to resource server failed")

    ############################
    def __removeClient(self, addr, port):
        badClient = None
        for client_id, peer in self.resource_peers.iteritems():
            if peer['addr'] == addr and peer['port'] == port:
                badClient = client_id
                break

        if badClient is not None:
            self.resource_peers[badClient]

    ############################
    def __removeOldSessions(self):
        cur_time = time.time()
        sessionsToRemove = []
        for session in self.sessions:
            if cur_time - session.last_message_time > self.last_message_time_threshold:
                sessionsToRemove.append(session)
        for session in sessionsToRemove:
            self.removeSession(session)

    ############################
    def _listening_established(self, port, **kwargs):
        TCPServer._listening_established(self, port, **kwargs)
        self.client.setResourcePort(self.cur_port)

