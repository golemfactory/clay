import time
import os
import logging

from collections import deque

from TaskManager import TaskManager
from TaskComputer import TaskComputer
from task_session import TaskSession
from TaskKeeper import TaskKeeper

from golem.ranking.Ranking import RankingStats
from golem.network.transport.tcp_network import TCPNetwork, TCPConnectInfo, TCPAddress, MidAndFilesProtocol
from golem.network.transport.network import ProtocolFactory, SessionFactory
from golem.network.transport.tcp_server import PendingConnectionsServer, PendingConnection, PenConnStatus

logger = logging.getLogger(__name__)


class TaskServer(PendingConnectionsServer):
    #############################
    def __init__(self, node, configDesc, keysAuth, client, useIp6=False):
        self.client             = client
        self.keysAuth           = keysAuth
        self.configDesc         = configDesc

        self.node               = node
        self.taskKeeper         = TaskKeeper()
        self.taskManager        = TaskManager(configDesc.clientUid, self.node, keyId = self.keysAuth.get_key_id(), rootPath = self.__getTaskManagerRoot(configDesc), useDistributedResources = configDesc.useDistributedResourceManagement)
        self.taskComputer       = TaskComputer(configDesc.clientUid, self)
        self.taskSessions       = {}
        self.taskSessionsIncoming = []

        self.maxTrust           = 1.0
        self.minTrust           = 0.0

        self.lastMessages       = []
        self.lastMessageTimeThreshold = configDesc.taskSessionTimeout

        self.resultsToSend      = {}
        self.failuresToSend     = {}

        self.useIp6=useIp6

        self.responseList = {}

        network = TCPNetwork(ProtocolFactory(MidAndFilesProtocol, self, SessionFactory(TaskSession)),  useIp6)
        PendingConnectionsServer.__init__(self, configDesc, network)

    #############################
    def start_accepting(self):
        PendingConnectionsServer.start_accepting(self)

    #############################
    def syncNetwork(self):
        self.taskComputer.run()
        self._sync_pending()
        self.__removeOldTasks()
        self.__sendWaitingResults()
        self.__removeOldSessions()
        self._remove_old_listenings()
        self.__sendPayments()
        self.__checkPayments()

    #############################
    # This method chooses random task from the network to compute on our machine
    def requestTask(self):

        theader = self.taskKeeper.getTask()
        if theader is not None:
            trust = self.client.getRequestingTrust(theader.clientId)
            logger.debug("Requesting trust level: {}".format(trust))
            if trust >= self.configDesc.requestingTrust:
                args = {
                        'clientId': self.configDesc.clientUid,
                        'keyId':  theader.taskOwnerKeyId,
                        'taskId': theader.taskId,
                        'estimatedPerformance': self.configDesc.estimatedPerformance,
                        'maxResourceSize': self.configDesc.maxResourceSize,
                        'maxMemorySize': self.configDesc.maxMemorySize,
                        'numCores': self.configDesc.numCores
                }
                self._add_pending_request(TaskConnTypes.TaskRequest, theader.taskOwner, theader.taskOwnerPort,
                                         theader.taskOwnerKeyId, args)

                return theader.taskId

        return 0

    #############################
    def requestResource(self, subtaskId, resourceHeader, address, port, keyId, taskOwner):
        args = {
            'keyId': keyId,
            'subtaskId': subtaskId,
            'resourceHeader': resourceHeader
        }
        self._add_pending_request(TaskConnTypes.ResourceRequest, taskOwner, port, keyId, args)
        return subtaskId

    #############################
    def pullResources(self, taskId, listFiles):
        self.client.pullResources(taskId, listFiles)

    #############################
    def sendResults(self, subtaskId, taskId, result, ownerAddress, ownerPort, ownerKeyId, owner, nodeId):

        if 'data' not in result or 'resultType' not in result:
            logger.error("Wrong result format")
            assert False

        self.client.increaseTrust(nodeId, RankingStats.requested)

        if subtaskId not in self.resultsToSend:
            self.taskKeeper.addToVerification(subtaskId, taskId)
            self.resultsToSend[subtaskId] = WaitingTaskResult(subtaskId, result['data'], result['resultType'], 0.0, 0.0,
                                                              ownerAddress, ownerPort, ownerKeyId, owner)
        else:
            assert False

        return True

    #############################
    def sendTaskFailed(self, subtaskId, taskId, errMsg, ownerAddress, ownerPort, ownerKeyId, owner, nodeId):
        self.client.decreaseTrust(nodeId, RankingStats.requested)
        if subtaskId not in self.failuresToSend:
            self.failuresToSend[subtaskId] = WaitingTaskFailure(subtaskId, errMsg, ownerAddress, ownerPort, ownerKeyId,
                                                                owner)

    #############################
    def newConnection(self, session):
        self.taskSessionsIncoming.append(session)

    new_connection = newConnection

    #############################
    def getTasksHeaders(self):
        ths =  self.taskKeeper.getAllTasks() + self.taskManager.getTasksHeaders()

        ret = []

        for th in ths:
            ret.append({    "id"            : th.taskId, 
                            "address"       : th.taskOwnerAddress,
                            "port"          : th.taskOwnerPort,
                            "keyId"         : th.taskOwnerKeyId,
                            "taskOwner"     : th.taskOwner,
                            "ttl"           : th.ttl,
                            "subtaskTimeout": th.subtaskTimeout,
                            "clientId"      : th.clientId,
                            "environment"   : th.environment,
                            "minVersion"    : th.minVersion })

        return ret

    #############################
    def addTaskHeader(self, thDictRepr):
        try:
            id = thDictRepr["id"]
            if id not in self.taskManager.tasks.keys(): # It is not my task id
                self.taskKeeper.addTaskHeader(thDictRepr,  self.client.supportedTask(thDictRepr))
            return True
        except Exception, err:
            logger.error("Wrong task header received {}".format(str(err)))
            return False

    #############################
    def removeTaskHeader(self, taskId):
        self.taskKeeper.removeTaskHeader(taskId)

    #############################
    def removeTaskSession(self, taskSession):
        pc = self.pending_connections.get(taskSession.conn_id)
        if pc:
            pc.status = PenConnStatus.Failure

        for tsk in self.taskSessions.keys():
            if self.taskSessions[tsk] == taskSession:
                del self.taskSessions[tsk]

    #############################
    def setLastMessage(self, type, t, msg, address, port):
        if len(self.lastMessages) >= 5:
            self.lastMessages = self.lastMessages[-4:]

        self.lastMessages.append([type, t, address, port, msg])

    #############################
    def getLastMessages(self):
        return self.lastMessages

    #############################
    def getWaitingTaskResult(self, subtask_id):
        return self.resultsToSend.get(subtask_id)

    #############################
    def getClientId(self):
        return self.configDesc.clientUid

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

    #############################
    def getResourceAddr(self) :
        return self.client.node.prvAddr

    #############################
    def getResourcePort(self) :
        return self.client.resourcePort

    #############################
    def getSubtaskTtl(self, taskId):
        return self.taskKeeper.getSubtaskTtl(taskId)

    #############################
    def addResourcePeer(self, clientId, addr, port, keyId, nodeInfo):
        self.client.addResourcePeer(clientId, addr, port, keyId, nodeInfo)

    #############################
    def taskResultSent(self, subtaskId):
        if subtaskId in self.resultsToSend:
            del self.resultsToSend[subtaskId]
        else:
            assert False

    #############################
    def change_config(self, configDesc):
        PendingConnectionsServer.change_config(self, configDesc)
        self.configDesc = configDesc
        self.lastMessageTimeThreshold = configDesc.taskSessionTimeout
        self.taskManager.change_config(self.__getTaskManagerRoot(configDesc), configDesc.useDistributedResourceManagement)
        self.taskComputer.change_config()

    ############################
    def changeTimeouts(self, taskId, fullTaskTimeout, subtaskTimeout, minSubtaskTime):
        self.taskManager.changeTimeouts(taskId, fullTaskTimeout, subtaskTimeout, minSubtaskTime)

    ############################
    def getTaskComputerRoot(self):
        return os.path.join(self.configDesc.rootPath, "ComputerRes")

    ############################
    def subtaskRejected(self, subtaskId):
        logger.debug("Subtask {} result rejected".format(subtaskId))
        taskId = self.taskKeeper.getWaitingForVerificationTaskId(subtaskId)
        if taskId is not None:
            self.decreaseTrustPayment(taskId)
            self.removeTaskHeader(taskId)
            self.taskKeeper.removeWaitingForVerificationTaskId(subtaskId)

    ############################
    def subtaskAccepted(self, taskId, reward):
        logger.debug("Task {} result accepted".format(taskId))

      #  taskId = self.taskKeeper.getWaitingForVerificationTaskId(taskId)
        if not self.taskKeeper.isWaitingForTask(taskId):
            logger.error("Wasn't waiting for reward for task {}".format(taskId))
            return
        try:
            logger.info("Getting {} for task {}".format(reward, taskId))
            self.client.getReward(int(reward))
            self.increaseTrustPayment(taskId)
        except ValueError:
            logger.error("Wrong reward amount {} for task {}".format(reward, taskId))
            self.decreaseTrustPayment(taskId)
        self.taskKeeper.removeWaitingForVerification(taskId)

    ############################
    def subtaskFailure(self, subtaskId, err):
        logger.info("Computation for task {} failed: {}.".format(subtaskId, err))
        nodeId = self.taskManager.getNodeIdForSubtask(subtaskId)
        self.client.decreaseTrust(nodeId, RankingStats.computed)
        self.taskManager.taskComputationFailure(subtaskId, err)

    ###########################
    def acceptResult(self, subtaskId, accountInfo):
        priceMod = self.taskManager.getPriceMod(subtaskId)
        taskId = self.taskManager.getTaskId(subtaskId)
        self.client.acceptResult(taskId, subtaskId, priceMod, accountInfo)

        mod = min(max(self.taskManager.getTrustMod(subtaskId), self.minTrust), self.maxTrust)
        self.client.increaseTrust(accountInfo.nodeId, RankingStats.computed, mod)

    ###########################
    def receiveTaskVerification(self, taskId):
        self.taskKeeper.receiveTaskVerification(taskId)

    ###########################
    def increaseTrustPayment(self, taskId):
        nodeId = self.taskKeeper.getReceiverForTaskVerificationResult(taskId)
        self.receiveTaskVerification(taskId)
        self.client.increaseTrust(nodeId, RankingStats.payment, self.maxTrust)

    ###########################
    def decreaseTrustPayment(self, taskId):
        nodeId = self.taskKeeper.getReceiverForTaskVerificationResult(taskId)
        self.receiveTaskVerification(taskId)
        self.client.decreaseTrust(nodeId, RankingStats.payment, self.maxTrust)

    ###########################
    def localPayForTask(self, taskId, address, port, keyId, nodeInfo, price):
        logger.info("Paying {} for task {}".format(price, taskId))
        args = {'keyId': keyId, 'taskId': taskId, 'price': price}
        self._add_pending_request(TaskConnTypes.PayForTask, nodeInfo, port, keyId, args)

    ###########################
    def globalPayForTask(self, taskId, payments):
        globalPayments = { ethAccount: desc.value for ethAccount, desc in payments.items() }
        self.client.globalPayForTask(taskId, globalPayments)
        for ethAccount, v in globalPayments.iteritems():
            print "Global paying {} to {}".format(v, ethAccount)

    ###########################
    def rejectResult(self, subtaskId, accountInfo):
        mod = min(max(self.taskManager.getTrustMod(subtaskId), self.minTrust), self.maxTrust)
        self.client.decreaseTrust(accountInfo.nodeId, RankingStats.wrongComputed, mod)
        args = {'keyId': accountInfo.keyId, 'subtaskId': subtaskId}
        self._add_pending_request(TaskConnTypes.ResultRejected, accountInfo.nodeInfo, accountInfo.port,
                                 accountInfo.keyId, args)

    ###########################
    def unpackDelta(self, destDir, delta, taskId):
        self.client.resourceServer.unpackDelta(destDir, delta, taskId)

    #############################
    def getComputingTrust(self, nodeId):
        return self.client.getComputingTrust(nodeId)

    #############################
    def startTaskSession(self, nodeInfo, superNodeInfo, conn_id):
        #FIXME Jaki port i adres startowy?
        args = {'keyId': nodeInfo.key, 'nodeInfo': nodeInfo, 'superNodeInfo': superNodeInfo, 'ansConnId': conn_id}
        self._add_pending_request(TaskConnTypes.StartSession, nodeInfo, nodeInfo.prvPort, nodeInfo.key, args)

    #############################
    def respondTo(self, keyId, session, conn_id):
        if conn_id in self.pending_connections:
            del self.pending_connections[conn_id]

        responses = self.responseList.get(keyId)
        if responses is None or len(responses) == 0:
            session.dropped()
            return

        res = responses.popleft()
        res(session)

    #############################
    def respondToMiddleman(self, keyId, session, conn_id, destKeyId):
        if destKeyId in self.responseList:
            self.respondTo(destKeyId, session, conn_id)
        else:
            logger.warning("No response for {}".format(destKeyId))
            session.dropped()


    #############################
    def beAMiddleman(self, keyId, openSession, conn_id, askingNode, destNode, askConnId):
        keyId = askingNode.key
        response = lambda session: self.__askingNodeForMiddlemanConnectionEstablished(session, conn_id, keyId, openSession,
                                                                                      askingNode, destNode, askConnId)
        if keyId in self.responseList:
            self.responseList[keyId].append(response)
        else:
            self.responseList[keyId] = deque([response])

        self.client.wantToStartTaskSession(keyId, self.node, conn_id)
        openSession.is_middleman = True

    #############################
    def waitForNatTraverse(self, port, session):
        session.close_now()
        args = {'superNode': session.extra_data['superNode'],
                'askingNode': session.extra_data['askingNode'],
                'destNode': session.extra_data['destNode'],
                'askConnId': session.extra_data['ansConnId']}
        self._add_pending_listening(TaskListenTypes.StartSession, port, args)

    #############################
    def organizeNatPunch(self, addr, port, clientKeyId, askingNode, destNode, ansConnId):
        self.client.informAboutTaskNatHole(askingNode.key, clientKeyId, addr, port, ansConnId)

    #############################
    def traverseNat(self, keyId, addr, port, conn_id, superKeyId):
        connect_info = TCPConnectInfo([TCPAddress(addr, port)], self.__connectionForTraverseNatEstablished,
                                      self.__connectionForTraverseNatFailure)
        self.network.connect(connect_info, clientKeyId=keyId, conn_id=conn_id, superKeyId=superKeyId)

    #############################
    def traverseNatFailure(self, conn_id):
        pc = self.pending_connections.get(conn_id)
        if pc:
            pc.failure(conn_id, *pc.args)

    #############################
    def _getFactory(self):
        return self.factory(self)

    #############################
    def _listening_established(self, port, **kwargs):
        self.cur_port = port
        logger.info(" Port {} opened - listening".format(self.cur_port))
        self.node.prvPort = self.cur_port
        self.taskManager.listenAddress = self.node.prvAddr
        self.taskManager.listenPort = self.cur_port
        self.taskManager.node = self.node

    #############################
    def _listening_failure(self, **kwargs):
        logger.error("Listening on ports {} to {} failure".format(self.configDesc.startPort, self.configDesc.endPort))
        #FIXME: some graceful terminations should take place here
        # sys.exit(0)

    #############################
    def _listeningForStartSessionEstablished(self, port, listenId, superNode, askingNode, destNode, askConnId):
        logger.debug("Listening on port {}".format(port))
        listening = self.open_listenings.get(listenId)
        if listening:
            self.listening.time = time.time()
            self.listening.listening_port = port
        else:
            logger.warning("Listening {} not in open listenings list".format(listenId))

    #############################
    def _listeningForStartSessionFailure(self, listenId, superNode, askingNode, destNode, askConnId):
        if listenId in self.open_listenings:
            del self.open_listenings['listenId']

        self.__connectionForNatPunchFailure(listenId, superNode, askingNode, destNode, askConnId)

    #############################
    #   CONNECTION REACTIONS    #
    #############################
    def __connectionForTaskRequestEstablished(self, session, conn_id, clientId, keyId, taskId, estimatedPerformance,
                                              maxResourceSize, maxMemorySize, numCores):
        session.task_id = taskId
        session.key_id = keyId
        session.conn_id = conn_id
        self._mark_connected(conn_id, session.address, session.port)
        self.taskSessions[taskId] = session
        session.send_hello()
        session.request_task(clientId, taskId, estimatedPerformance, maxResourceSize, maxMemorySize, numCores)

    #############################
    def __connectionForTaskRequestFailure(self, conn_id, clientId, keyId, taskId, estimatedPerformance, maxResourceSize,
                                          maxMemorySize, numCores, *args):

        response = lambda session: self.__connectionForTaskRequestEstablished(session, conn_id, clientId, keyId, taskId,
                                                                                estimatedPerformance, maxResourceSize,
                                                                                maxMemorySize, numCores)
        if keyId in self.responseList:
            self.responseList[keyId].append(response)
        else:
            self.responseList[keyId] = deque([response])

        self.client.wantToStartTaskSession(keyId, self.node, conn_id)

        pc = self.pending_connections.get(conn_id)
        if pc:
            pc.status = PenConnStatus.WaitingAlt
            pc.time = time.time()

    #############################
    def __connectionForTaskResultEstablished(self, session, conn_id, keyId, waitingTaskResult):
        session.key_id = keyId
        session.conn_id = conn_id
        self._mark_connected(conn_id, session.address, session.port)
        self.taskSessions[waitingTaskResult.subtask_id] = session

        session.send_hello()
        session.send_report_computed_task(waitingTaskResult, self.node.prvAddr, self.cur_port, self.client.getEthAccount(),
                                       self.node)

    #############################
    def __connectionForTaskResultFailure(self, conn_id, keyId, waitingTaskResult):

        response = lambda session: self.__connectionForTaskResultEstablished(session, conn_id, keyId, waitingTaskResult)

        if keyId in self.responseList:
            self.responseList[keyId].append(response)
        else:
            self.responseList[keyId] = deque([response])

        self.client.wantToStartTaskSession(keyId, self.node, conn_id)

        pc = self.pending_connections.get(conn_id)
        if pc:
            pc.status = PenConnStatus.WaitingAlt
            pc.time = time.time()


    #############################
    def __connectionForTaskFailureEstablished(self, session, conn_id, keyId, subtaskId, errMsg):
        session.key_id = keyId
        session.conn_id = conn_id
        self._mark_connected(conn_id, session.address, session.port)
        self.taskSessions[subtaskId] = session
        session.send_hello()
        session.send_task_failure(subtaskId, errMsg)

    #############################
    def __connectionForTaskFailureFailure(self, conn_id, keyId, subtaskId, errMsg):

        response = lambda session: self.__connectionForTaskFailureEstablished(session, conn_id, keyId, subtaskId, errMsg)

        if keyId in self.responseList:
            self.responseList[keyId].append(response)
        else:
            self.responseList[keyId] = deque([response])

        self.client.wantToStartTaskSession(keyId, self.node, conn_id)

        pc = self.pending_connections.get(conn_id)
        if pc:
            pc.status = PenConnStatus.WaitingAlt
            pc.time = time.time()

    #############################
    def __connectionForResourceRequestEstablished(self, session, conn_id, keyId, subtaskId, resourceHeader):

        session.key_id = keyId
        session.task_id = subtaskId
        session.conn_id = conn_id
        self._mark_connected(conn_id, session.address, session.port)
        self.taskSessions[subtaskId] = session
        session.send_hello()
        session.request_resource(subtaskId, resourceHeader)

    #############################
    def __connectionForResourceRequestFailure(self, conn_id, keyId, subtaskId, resourceHeader):

        response = lambda session: self.__connectionForResourceRequestEstablished(session, conn_id, keyId, subtaskId,
                                                                                  resourceHeader)
        if keyId in self.responseList:
            self.responseList[keyId].append(response)
        else:
            self.responseList[keyId] = deque([response])

        self.client.wantToStartTaskSession(keyId, self.node, conn_id)

        pc = self.pending_connections.get(conn_id)
        if pc:
            pc.status = PenConnStatus.WaitingAlt
            pc.time = time.time()

    #############################
    def __connectionForResultRejectedEstablished(self, session, conn_id, keyId, subtaskId):
        session.key_id = keyId
        session.conn_id = conn_id
        self._mark_connected(conn_id, session.address, session.port)
        session.send_hello()
        session.send_result_rejected(subtaskId)

    #############################
    def __connectionForResultRejectedFailure(self, conn_id, keyId, subtaskId):

        response = lambda session: self.__connectionForResultRejectedFailure(session, conn_id, keyId, subtaskId)

        if keyId in self.responseList:
            self.responseList[keyId].append(response)
        else:
            self.responseList[keyId] = deque([response])

        self.client.wantToStartTaskSession(keyId, self.node, conn_id)
        pc = self.pending_connections.get(conn_id)
        if pc:
            pc.status = PenConnStatus.WaitingAlt
            pc.time = time.time()

    #############################
    def __connectionForPayForTaskEstablished(self, session, conn_id, keyId, taskId, price):
        session.key_id = keyId
        session.conn_id = conn_id
        self._mark_connected(conn_id, session.address, session.port)
        session.send_hello()
        session.send_reward_for_task(taskId, price)
        self.client.taskRewardPaid(taskId, price)

    #############################
    def __connectionForPayForTaskFailure(self, conn_id, keyId, taskId, price):

        response = lambda session: self.__connectionForPayForTaskEstablished(session, conn_id, keyId, taskId,
                                                                             price)

        if keyId in self.responseList:
            self.responseList[keyId].append(response)
        else:
            self.responseList[keyId] = deque([response])

        self.client.wantToStartTaskSession(keyId, self.node, conn_id)

        pc = self.pending_connections.get(conn_id)
        if pc:
            pc.status = PenConnStatus.WaitingAlt
            pc.time = time.time()

    #############################
    def __connectionForStartSessionEstablished(self, session, conn_id, keyId, nodeInfo, superNodeInfo, ansConnId):
        session.key_id = keyId
        session.conn_id = conn_id
        self._mark_connected(conn_id, session.address, session.port)
        session.send_hello()
        session.send_start_session_response(ansConnId)

    #############################
    def __connectionForStartSessionFailure(self, conn_id, keyId, nodeInfo, superNodeInfo, ansConnId):
        logger.info("Failed to start requested task session for node {}".format(keyId))
        self.final_conn_failure(conn_id)
        #TODO CO w takiej sytuacji?
        if superNodeInfo is None:
            logger.info("Permanently can't connect to node {}".format(keyId))
            return

        #FIXME To powinno zostac przeniesione do jakiejs wyzszej polaczeniowej instalncji
        if self.node.natType in TaskServer.supported_nat_types:
            args = {
                'superNode': superNodeInfo,
                'askingNode': nodeInfo,
                'destNode': self.node,
                'ansConnId': ansConnId
            }
            self._add_pending_request(TaskConnTypes.NatPunch, superNodeInfo, superNodeInfo.prvPort, superNodeInfo.key,
                                    args)
        else:
            args = {
                'keyId': superNodeInfo.key,
                'askingNodeInfo': nodeInfo,
                'selfNodeInfo': self.node,
                'ansConnId': ansConnId
            }
            self._add_pending_request(TaskConnTypes.Middleman, superNodeInfo, superNodeInfo.prvPort, superNodeInfo.key,
                                    args)
        #TODO Dodatkowe usuniecie tego zadania (bo zastapione innym)

    #############################
    def __connectionForNatPunchEstablished(self, session, conn_id, superNode, askingNode, destNode, ansConnId):
        session.key_id = superNode.key
        session.conn_id = conn_id
        session.extra_data = {'superNode': superNode, 'askingNode': askingNode, 'destNode': destNode,
                             'ansConnId': ansConnId}
        session.send_hello()
        session.send_nat_punch(askingNode, destNode, ansConnId)

    #############################
    def __connectionForNatPunchFailure(self, conn_id, superNode, askingNode, destNode, ansConnId):
        self.final_conn_failure(conn_id)
        args = {
            'keyId': superNode.key,
            'askingNodeInfo': askingNode,
            'selfNodeInfo': destNode,
            'ansConnId': ansConnId
        }
        self._add_pending_request(TaskConnTypes.Middleman, superNode, superNode.prvPort,
                                superNode.key, args)

    #############################
    def __connectionForTraverseNatEstablished(self, session, clientKeyId, conn_id, superKeyId):
        self.respondTo(clientKeyId, session, conn_id) #FIXME

    #############################
    def __connectionForTraverseNatFailure(self, clientKeyId, conn_id, superKeyId):
        logger.error("Connection for traverse nat failure")
        self.client.informAboutNatTraverseFailure(superKeyId, clientKeyId, conn_id)
        pass #TODO Powinnismy powiadomic serwer o nieudanej probie polaczenia

    #############################
    def __connectionForMiddlemanEstablished(self, session, conn_id, keyId, askingNodeInfo, selfNodeInfo, ansConnId):
        session.key_id = keyId
        session.conn_id = conn_id
        session.send_hello()
        session.send_middleman(askingNodeInfo, selfNodeInfo, ansConnId)

    #############################
    def __connectionForMiddlemanFailure(self, conn_id, keyId, askingNodeInfo, selfNodeInfo, ansConnId):
        self.final_conn_failure(conn_id)
        logger.info("Permanently can't connect to node {}".format(keyId))
        return

    #############################
    def __askingNodeForMiddlemanConnectionEstablished(self, session, conn_id, keyId, openSession,  askingNode, destNode,
                                                      ansConnId):
        session.key_id = keyId
        session.conn_id = conn_id
        session.send_hello()
        session.send_join_middleman_conn(keyId, ansConnId, destNode.key)
        session.open_session = openSession
        openSession.open_session = session

    def __connectionForTaskRequestFinalFailure(self, conn_id, clientId, keyId, taskId, estimatedPerformance,
                                               maxResourceSize, maxMemorySize, numCores, *args):
        logger.warning("Cannot connect to task {} owner".format(taskId))
        logger.warning("Removing task {} from task list".format(taskId))

        self.taskComputer.taskRequestRejected(taskId, "Connection failed")
        self.taskKeeper.requestFailure(taskId)

    def __connectionForPayForTaskFinalFailure(self, conn_id, keyId, taskId, price):
        logger.warning("Cannot connect to pay for task {} ".format(taskId))
        self.client.taskRewardPaymentFailure(taskId, price)

    def __connectionForResourceRequestFinalFailure(self, conn_id, keyId, subtaskId, resourceHeader):
        logger.warning("Cannot connect to task {} owner".format(subtaskId))
        logger.warning("Removing task {} from task list".format(subtaskId))

        self.taskComputer.resourceRequestRejected(subtaskId, "Connection failed")
        self.removeTaskHeader(subtaskId)

    def __connectionForResultRejectedFinalFailure(self, conn_id, keyId, subtaskId):
        logger.warning("Cannot connect to deliver information about rejected result for task {}".format(subtaskId))

    def __connectionForTaskResultFinalFailure(self, conn_id, keyId, waitingTaskResult):
        logger.warning("Cannot connect to task {} owner".format(waitingTaskResult.subtaskId))

        waitingTaskResult.lastSendingTrial  = time.time()
        waitingTaskResult.delayTime         = self.configDesc.maxResultsSendingDelay
        waitingTaskResult.alreadySending    = False

    def __connectionForTaskFailureFinalFailure(self, conn_id, keyId, subtaskId, errMsg):
       logger.warning("Cannot connect to task {} owner".format(subtaskId))

    def __connectionForStartSessionFinalFailure(self, conn_id, keyId, nodeInfo, superNodeInfo, ansConnId):
        logger.warning("Starting sesion for {} impossible".format(keyId))

    def __connectionForMiddlemanFinalFailure(self, *args):
        pass

    def __connectionForNatPunchFinalFailure(self, *args):
        pass

    #SYNC METHODS
    #############################
    def __removeOldTasks(self):
        self.taskKeeper.removeOldTasks()
        nodesWithTimeouts = self.taskManager.removeOldTasks()
        for nodeId in nodesWithTimeouts:
            self.client.decreaseTrust(nodeId, RankingStats.computed)

    #############################
    def __removeOldSessions(self):
        curTime = time.time()
        sessionsToRemove = []
        for subtaskId, session in self.taskSessions.iteritems():
            if curTime - session.last_message_time > self.lastMessageTimeThreshold:
                sessionsToRemove.append(subtaskId)
        for subtaskId in sessionsToRemove:
            if self.taskSessions[subtaskId].task_computer is not None:
                self.taskSessions[subtaskId].task_computer.sessionTimeout()
            self.taskSessions[subtaskId].dropped()

    #############################
    def __sendWaitingResults(self):
        for wtr in self.resultsToSend.itervalues():

            if not wtr.already_sending:
                if time.time() - wtr.last_sending_trial > wtr.delay_time:
                    wtr.already_sending = True
                    args = {'keyId': wtr.owner_key_id, 'waitingTaskResult': wtr}
                    self._add_pending_request(TaskConnTypes.TaskResult, wtr.owner, wtr.owner_port, wtr.owner_key_id, args)

        for wtf in self.failuresToSend.itervalues():
            args = {'keyId': wtf.ownerKeyId, 'subtaskId': wtf.subtaskId, 'errMsg': wtf.errMsg}
            self._add_pending_request(TaskConnTypes.TaskFailure, wtf.owner, wtf.ownerPort, wtf.ownerKeyId, args)

        self.failuresToSend.clear()

    #############################
    def __sendPayments(self):
        taskId, payments = self.client.getNewPaymentsTasks()
        if payments:
            self.globalPayForTask(taskId, payments)
            for payment in payments.itervalues():
                for idx,account in enumerate(payment.accounts):
                    self.localPayForTask(taskId, account.addr, account.port, account.keyId, account.nodeInfo,
                                         payment.accountsPayments[idx])

    #############################
    def __checkPayments(self):
        afterDeadline = self.taskKeeper.checkPayments()
        for taskId in afterDeadline:
            self.decreaseTrustPayment(taskId)

    #CONFIGURATION METHODS
    #############################
    def __getTaskManagerRoot(self, configDesc):
        return os.path.join(configDesc.rootPath, "res")

    #############################
    def _set_conn_established(self):
        self.conn_established_for_type.update({
            TaskConnTypes.TaskRequest: self.__connectionForTaskRequestEstablished,
            TaskConnTypes.PayForTask: self.__connectionForPayForTaskEstablished,
            TaskConnTypes.ResourceRequest: self.__connectionForResourceRequestEstablished,
            TaskConnTypes.ResultRejected: self.__connectionForResultRejectedEstablished,
            TaskConnTypes.TaskResult: self.__connectionForTaskResultEstablished,
            TaskConnTypes.TaskFailure: self.__connectionForTaskFailureEstablished,
            TaskConnTypes.StartSession: self.__connectionForStartSessionEstablished,
            TaskConnTypes.Middleman: self.__connectionForMiddlemanEstablished,
            TaskConnTypes.NatPunch: self.__connectionForNatPunchEstablished, #NATPUNADD
        })

    #############################
    def _set_conn_failure(self):
        self.conn_failure_for_type.update({
            TaskConnTypes.TaskRequest: self.__connectionForTaskRequestFailure,
            TaskConnTypes.PayForTask: self.__connectionForPayForTaskFailure,
            TaskConnTypes.ResourceRequest: self.__connectionForResourceRequestFailure,
            TaskConnTypes.ResultRejected: self.__connectionForResultRejectedFailure,
            TaskConnTypes.TaskResult: self.__connectionForTaskResultFailure,
            TaskConnTypes.TaskFailure: self.__connectionForTaskFailureFailure,
            TaskConnTypes.StartSession: self.__connectionForStartSessionFailure,
            TaskConnTypes.Middleman: self.__connectionForMiddlemanFailure,
            TaskConnTypes.NatPunch: self.__connectionForNatPunchFailure
        })

    def _set_conn_final_failure(self):
        self.conn_final_failure_for_type.update({
            TaskConnTypes.TaskRequest: self.__connectionForTaskRequestFinalFailure,
            TaskConnTypes.PayForTask: self.__connectionForPayForTaskFinalFailure,
            TaskConnTypes.ResourceRequest: self.__connectionForResourceRequestFinalFailure,
            TaskConnTypes.ResultRejected: self.__connectionForResultRejectedFinalFailure,
            TaskConnTypes.TaskResult: self.__connectionForTaskResultFinalFailure,
            TaskConnTypes.TaskFailure: self.__connectionForTaskFailureFinalFailure,
            TaskConnTypes.StartSession: self.__connectionForStartSessionFinalFailure,
            TaskConnTypes.Middleman: self.__connectionForMiddlemanFinalFailure,
            TaskConnTypes.NatPunch: self.__connectionForNatPunchFinalFailure
        })

    #############################
    def _set_listen_established(self):
        self.listenEstablishedForType.update({
          TaskListenTypes.StartSession: self._listeningForStartSessionEstablished
        })

    #############################
    def _set_listen_failure(self):
        self.listenFailureForType.update({
          TaskListenTypes.StartSession: self._listeningForStartSessionFailure
        })

##########################################################

class WaitingTaskResult:
    #############################
    def __init__(self, subtask_id, result, result_type, last_sending_trial, delay_time, owner_address, owner_port,
                 owner_key_id, owner):
        self.subtask_id = subtask_id
        self.result = result
        self.result_type = result_type
        self.last_sending_trial = last_sending_trial
        self.delay_time = delay_time
        self.owner_address = owner_address
        self.owner_port = owner_port
        self.owner_key_id = owner_key_id
        self.owner = owner
        self.already_sending = False

##########################################################

class WaitingTaskFailure:
    #############################
    def __init__(self, subtaskId, errMsg, ownerAddress, ownerPort, ownerKeyId, owner):
        self.subtaskId = subtaskId
        self.ownerAddress = ownerAddress
        self.ownerPort = ownerPort
        self.ownerKeyId = ownerKeyId
        self.owner = owner
        self.errMsg = errMsg


##########################################################
class TaskConnTypes:
    TaskRequest = 1
    ResourceRequest = 2
    ResultRejected = 3
    PayForTask = 4
    TaskResult = 5
    TaskFailure = 6
    StartSession = 7
    Middleman = 8
    NatPunch = 9

class TaskListenTypes:
    StartSession = 1


