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
    def __init__(self, config_desc, keysAuth, client, useIp6=False):
        self.client = client
        self.keysAuth = keysAuth
        self.resourcesToSend = []
        self.resourcesToGet = []
        self.resSendIt = 0
        self.peersIt = 0
        self.dirManager = DirManager(config_desc.rootPath, config_desc.clientUid)
        self.resourceManager = DistributedResourceManager(self.dirManager.getResourceDir())
        self.useIp6=useIp6
        network = TCPNetwork(ProtocolFactory(FilesProtocol, self, SessionFactory(ResourceSession)),  useIp6)
        TCPServer.__init__(self, config_desc, network)

        self.resourcePeers = {}
        self.waitingTasks = {}
        self.waitingTasksToCompute = {}
        self.waitingResources = {}

        self.lastGetResourcePeersTime  = time.time()
        self.getResourcePeersInterval = 5.0
        self.sessions = []

        self.lastMessageTimeThreshold = config_desc.resourceSessionTimeout

    ############################
    def startAccepting(self):
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
    def getPeers(self):
        self.client.getResourcePeers()

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
    def addResourcePeer(self, clientId, addr, port, keyId, nodeInfo):
        if clientId in self.resourcePeers:
            if self.resourcePeers[clientId]['addr'] == addr and self.resourcePeers[clientId]['port'] == port and self.resourcePeers[clientId]['keyId']:
                return

        self.resourcePeers[clientId] = { 'addr': addr, 'port': port, 'keyId': keyId, 'state': 'free', 'posResource': 0,
                                           'node': nodeInfo}

    ############################
    def setResourcePeers(self, resourcePeers):
        if self.config_desc.clientUid in resourcePeers:
            del resourcePeers[self.config_desc.clientUid]

        for clientId, [addr, port, keyId, nodeInfo] in resourcePeers.iteritems():
            self.addResourcePeer(clientId, addr, port, keyId, nodeInfo)

    ############################
    def syncNetwork(self):
        if len(self.resourcesToGet) + len(self.resourcesToSend) > 0:
            curTime = time.time()
            if curTime - self.lastGetResourcePeersTime > self.getResourcePeersInterval:
                self.client.getResourcePeers()
                self.lastGetResourcePeersTime = time.time()
        self.sendResources()
        self.getResources()
        self.__removeOldSessions()

    ############################
    def getResources(self):
        if len (self.resourcesToGet) == 0:
            return
        resourcePeers = [peer for peer in self.resourcePeers.values() if peer['state'] == 'free']
        random.shuffle(resourcePeers)

        if len (self.resourcePeers) == 0:
            return

        for peer in resourcePeers:
            peer['state'] = 'waiting'
            self.pullResource(self.resourcesToGet[0][0], peer['addr'], peer['port'], peer['keyId'], peer['node'])


    ############################
    def sendResources(self):
        if len(self.resourcesToSend) == 0:
            return

        if self.resSendIt >= len(self.resourcesToSend):
            self.resSendIt = len(self.resourcesToSend) - 1

        resourcePeers = [peer for peer in self.resourcePeers.values() if peer['state'] == 'free']

        for peer in resourcePeers:
            name = self.resourcesToSend[self.resSendIt][0]
            num = self.resourcesToSend[self.resSendIt][2]
            peer['state'] = 'waiting'
            self.pushResource(name , peer['addr'], peer['port'] , peer['keyId'], peer['node'], num)
            self.resSendIt = (self.resSendIt + 1) % len(self.resourcesToSend)

    ############################
    def pullResource(self, resource, addr, port, keyId, nodeInfo):
        tcp_addresses = self.__nodeInfoToTCPAddresses(nodeInfo, port)
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
    def pushResource(self, resource, addr, port, keyId, nodeInfo, copies):

        tcp_addresses = self.__nodeInfoToTCPAddresses(nodeInfo, port)
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
        clientId = self.__freePeer(address, port)
        if not self.resourceManager.checkResource(resource):
            logger.error("Wrong resource downloaded\n")
            if clientId is not None:
                self.client.decreaseTrust(clientId, RankingStats.resource)
            return
        if clientId is not None:
            # Uaktualniamy ranking co 100 zasobow, zeby specjalnie nie zasmiecac sieci
            self.resourcePeers[clientId]['posResource'] += 1
            if (self.resourcePeers[clientId]['posResource'] % 50) == 0:
                self.client.increaseTrust(clientId, RankingStats.resource, 50)
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
        return self.keysAuth.get_key_id()

    #############################
    def encrypt(self, message, publicKey):
        if publicKey == 0:
            return message
        return self.keysAuth.encrypt(message, publicKey)

    #############################
    def decrypt(self, message):
        return self.keysAuth.decrypt(message)

    #############################
    def sign(self, data):
        return self.keysAuth.sign(data)

    #############################
    def verifySig(self, sig, data, publicKey):
        return self.keysAuth.verify(sig, data, publicKey)


    ############################
    def changeConfig(self, config_desc):
        self.lastMessageTimeThreshold = config_desc.resourceSessionTimeout

    @staticmethod
    def __nodeInfoToTCPAddresses(nodeInfo, port):
        tcp_addresses = [TCPAddress(i, port) for i in nodeInfo.prvAddresses]
        if nodeInfo.pubPort:
            tcp_addresses.append(TCPAddress(nodeInfo.pubAddr, nodeInfo.pubPort))
        else:
            tcp_addresses.append(TCPAddress(nodeInfo.pubAddr, port))
        return tcp_addresses

    ############################
    def __freePeer(self, addr, port):
        for clientId, value in self.resourcePeers.iteritems():
            if value['addr'] == addr and value['port'] == port:
                self.resourcePeers[clientId]['state'] = 'free'
                return clientId


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
        for clientId, peer in self.resourcePeers.iteritems():
            if peer['addr'] == addr and peer['port'] == port:
                badClient = clientId
                break

        if badClient is not None:
            self.resourcePeers[badClient]

    ############################
    def __removeOldSessions(self):
        curTime = time.time()
        sessionsToRemove = []
        for session in self.sessions:
            if curTime - session.last_message_time > self.lastMessageTimeThreshold:
                sessionsToRemove.append(session)
        for session in sessionsToRemove:
            self.removeSession(session)

    ############################
    def _listening_established(self, port, **kwargs):
        TCPServer._listening_established(self, port, **kwargs)
        self.client.setResourcePort(self.cur_port)

