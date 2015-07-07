import time
import os
import logging

from collections import deque

from TaskManager import TaskManager
from TaskComputer import TaskComputer
from TaskSession import TaskSession
from TaskKeeper import TaskKeeper

from golem.network.transport.Tcp import Network, HostData, nodeInfoToHostInfos
from golem.ranking.Ranking import RankingStats
from golem.network.GNRServer import PendingConnectionsServer, PendingConnection, PenConnStatus
from golem.core.hostaddress import getExternalAddress

logger = logging.getLogger(__name__)

class TaskServer(PendingConnectionsServer):
    #############################
    def __init__(self, node, configDesc, keysAuth, client, useIp6=False):
        self.client             = client
        self.keysAuth           = keysAuth
        self.configDesc         = configDesc

        self.node               = node
        self.taskKeeper         = TaskKeeper()
        self.taskManager        = TaskManager(configDesc.clientUid, self.node, keyId = self.keysAuth.getKeyId(), rootPath = self.__getTaskManagerRoot(configDesc), useDistributedResources = configDesc.useDistributedResourceManagement)
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

        PendingConnectionsServer.__init__(self, configDesc, TaskServerFactory, TaskSession, useIp6)

    #############################
    def syncNetwork(self):
        self.taskComputer.run()
        self._syncPending()
        self.__removeOldTasks()
        self.__sendWaitingResults()
        self.__removeOldSessions()
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
                args = (self.configDesc.clientUid, theader.taskOwnerKeyId, theader.taskId,
                        self.configDesc.estimatedPerformance, self.configDesc.maxResourceSize,
                        self.configDesc.maxMemorySize, self.configDesc.numCores)
                self._addPendingRequest(TaskConnTypes.TaskRequest, theader.taskOwner, theader.taskOwnerPort,
                                         theader.taskOwnerKeyId, args)

                return theader.taskId

        return 0

    #############################
    def requestResource(self, subtaskId, resourceHeader, address, port, keyId, taskOwner):
        args = (keyId, subtaskId, resourceHeader)
        self._addPendingRequest(TaskConnTypes.ResourceRequest, taskOwner, port, keyId, args)
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

        session.taskServer = self
        session.taskComputer = self.taskComputer
        session.taskManager = self.taskManager

        self.taskSessionsIncoming.append(session)

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
        pc = self.pendingConnections.get(taskSession.connId)
        if pc is not None:
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
    def getWaitingTaskResult(self, subtaskId):
        if subtaskId in self.resultsToSend:
            return self.resultsToSend[subtaskId]
        else:
            return None

    #############################
    def getClientId(self):
        return self.configDesc.clientUid

    #############################
    def getKeyId(self):
        return self.keysAuth.getKeyId()

    #############################
    def encrypt(self, message, publicKey):
        if publicKey == 0:
            return message
        return self.keysAuth.encrypt(message, publicKey)

    #############################
    def decrypt(self, message):
        return self.keysAuth.decrypt(message)

    #############################
    def signData(self, data):
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
    def changeConfig(self, configDesc):
        PendingConnectionsServer.changeConfig(self, configDesc)
        self.configDesc = configDesc
        self.lastMessageTimeThreshold = configDesc.taskSessionTimeout
        self.taskManager.changeConfig(self.__getTaskManagerRoot(configDesc), configDesc.useDistributedResourceManagement)
        self.taskComputer.changeConfig()

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
        args = (keyId, taskId, price)
        self._addPendingRequest(TaskConnTypes.PayForTask, nodeInfo, port, keyId, args)

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
        args = (accountInfo.keyId, subtaskId)
        self._addPendingRequest(TaskConnTypes.ResultRejected, accountInfo.nodeInfo, accountInfo.port,
                                 accountInfo.keyId, args)

    ###########################
    def unpackDelta(self, destDir, delta, taskId):
        self.client.resourceServer.unpackDelta(destDir, delta, taskId)

    #############################
    def getComputingTrust(self, nodeId):
        return self.client.getComputingTrust(nodeId)

    #############################
    def startTaskSession(self, nodeInfo, superNodeInfo):
        #FIXME Jaki port i adres startowy?
        args = (nodeInfo.key, nodeInfo, superNodeInfo)
        self._addPendingRequest(TaskConnTypes.StartSession, nodeInfo, nodeInfo.prvPort, nodeInfo.key, args)

    #############################
    def respondTo(self, keyId, session, connId):
        responses = self.responseList.get(keyId)
        if responses is None or len(responses) == 0:
            session.dropped()
            return

        res = responses.popleft()
        res(session)

    #############################
    def respondToMiddleman(self, keyId, session, connId, destKeyId):
        if destKeyId in self.responseList:
            self.respondTo(destKeyId, session, connId)
        else:
            logger.warning("No response for {}".format(destKeyId))
            session.dropped()


    #############################
    def beAMiddleman(self, keyId, openSession, connId, askingNode, destNode, askConnId):
        keyId = askingNode.key
        response = lambda session: self.__askingNodeForMiddlemanConnectionEstablished(session, connId, keyId, openSession,
                                                                                      askingNode, destNode, askConnId)
        if keyId in self.responseList:
            self.responseList[keyId].append(response)
        else:
            self.responseList[keyId] = deque([response])

        self.client.wantToStartTaskSession(keyId, self.node, connId)
        openSession.isMiddleman = True

    #############################
    def _getFactory(self):
        return self.factory(self)

    #############################
    def _listeningEstablished(self, iListeningPort):
        self.curPort = iListeningPort.getHost().port
        self.iListeningPort = iListeningPort
        logger.info(" Port {} opened - listening".format(self.curPort))
        self.node.prvPort = self.curPort
        self.taskManager.listenAddress = self.node.prvAddr
        self.taskManager.listenPort = self.curPort
        self.taskManager.node = self.node

    #############################
    def _listeningFailure(self, *args):
        logger.error("Listening on ports {} to {} failure".format(self.configDesc.startPort, self.configDesc.endPort))
        #FIXME: some graceful terminations should take place here
        # sys.exit(0)

    #############################
    #   CONNECTION REACTIONS    #
    #############################
    def __connectionForTaskRequestEstablished(self, session, connId, clientId, keyId, taskId, estimatedPerformance,
                                              maxResourceSize, maxMemorySize, numCores):

        session.taskId = taskId
        session.clientKeyId = keyId
        session.taskServer = self
        session.taskComputer = self.taskComputer
        session.taskManager = self.taskManager
        session.connId = connId
        self._markConnected(connId, session.address, session.port)
        self.taskSessions[taskId] = session
        session.sendHello()
        session.requestTask(clientId, taskId, estimatedPerformance, maxResourceSize, maxMemorySize, numCores)

    #############################
    def __connectionForTaskRequestFailure(self, connId, clientId, keyId, taskId, estimatedPerformance, maxResourceSize,
                                          maxMemorySize, numCores, *args):
        logger.warning("Cannot connect to task {} owner".format(taskId))
        logger.warning("Removing task {} from task list".format(taskId))

        response = lambda session: self.__connectionForTaskRequestEstablished(session, connId, clientId, keyId, taskId,
                                                                                estimatedPerformance, maxResourceSize,
                                                                                maxMemorySize, numCores)
        if keyId in self.responseList:
            self.responseList[keyId].append(response)
        else:
            self.responseList[keyId] = deque([response])

        self.client.wantToStartTaskSession(keyId, self.node, connId)

        # FIXME Co zrobic jak ponowne polaczenie sie nie powiedzie
#        self.taskComputer.taskRequestRejected(taskId, "Connection failed")
#        self.taskKeeper.requestFailure(taskId)

    #############################
    def __connectionForTaskResultEstablished(self, session, connId, keyId, waitingTaskResult):
        session.taskServer = self
        session.taskComputer = self.taskComputer
        session.taskManager = self.taskManager
        session.clientKeyId = keyId
        session.connId = connId
        self._markConnected(connId, session.address, session.port)
        self.taskSessions[waitingTaskResult.subtaskId] = session

        session.sendHello()
        session.sendReportComputedTask(waitingTaskResult, self.node.prvAddr, self.curPort, self.client.getEthAccount(),
                                       self.node)

    #############################
    def __connectionForTaskResultFailure(self, connId, keyId, waitingTaskResult):
        logger.warning("Cannot connect to task {} owner".format(waitingTaskResult.subtaskId))

        response = lambda session: self.__connectionForTaskResultEstablished(session, connId, keyId, waitingTaskResult)

        if keyId in self.responseList:
            self.responseList[keyId].append(response)
        else:
            self.responseList[keyId] = deque([response])

        self.client.wantToStartTaskSession(keyId, self.node, connId)

# FIXME Do przelozenia w jakies miejsce w momencie, gdy kolejne proby polaczenia sie nie powioda
#        waitingTaskResult.lastSendingTrial  = time.time()
#        waitingTaskResult.delayTime         = self.configDesc.maxResultsSendingDelay
#        waitingTaskResult.alreadySending    = False

    #############################
    def __connectionForTaskFailureEstablished(self, session, connId, keyId, subtaskId, errMsg):
        session.taskServer = self
        session.clientKeyId = keyId
        session.connId = connId
        self._markConnected(connId, session.address, session.port)
        self.taskSessions[subtaskId] = session
        session.sendHello()
        session.sendTaskFailure(subtaskId, errMsg)

    #############################
    def __connectionForTaskFailureFailure(self, connId, keyId, subtaskId, errMsg):
        logger.warning("Cannot connect to task {} owner".format(subtaskId))

        response = lambda session: self.__connectionForTaskFailureEstablished(session, connId, keyId, subtaskId, errMsg)

        if keyId in self.responseList:
            self.responseList[keyId].append(response)
        else:
            self.responseList[keyId] = deque([response])

        self.client.wantToStartTaskSession(keyId, self.node, connId)

    #############################
    def __connectionForResourceRequestEstablished(self, session, connId, keyId, subtaskId, resourceHeader):

        session.taskServer = self
        session.taskComputer = self.taskComputer
        session.taskManager = self.taskManager
        session.clientKeyId = keyId
        session.taskId = subtaskId
        session.connId = connId
        self._markConnected(connId, session.address, session.port)
        self.taskSessions[subtaskId] = session
        session.sendHello()
        session.requestResource(subtaskId, resourceHeader)

    #############################
    def __connectionForResourceRequestFailure(self, connId, keyId, subtaskId, resourceHeader):
        logger.warning("Cannot connect to task {} owner".format(subtaskId))
   #     logger.warning("Removing task {} from task list".format(subtaskId))

        response = lambda session: self.__connectionForResourceRequestEstablished(session, connId, keyId, subtaskId,
                                                                                  resourceHeader)
        if keyId in self.responseList:
            self.responseList[keyId].append(response)
        else:
            self.responseList[keyId] = deque([response])

        self.client.wantToStartTaskSession(keyId, self.node, connId)
        #FIXME do przelozenia w jakies miejsce po zareagowaniu na blad
        #self.taskComputer.resourceRequestRejected(subtaskId, "Connection failed")
        
        #self.removeTaskHeader(subtaskId)

    #############################
    def __connectionForResultRejectedEstablished(self, session, connId, keyId, subtaskId):
        session.taskServer = self
        session.taskComputer = self.taskComputer
        session.taskManager = self.taskManager
        session.clientKeyId = keyId
        session.connId = connId
        self._markConnected(connId, session.address, session.port)
        session.sendHello()
        session.sendResultRejected(subtaskId)

    #############################
    def __connectionForResultRejectedFailure(self, connId, keyId, subtaskId):
        logger.warning("Cannot connect to deliver information about rejected result for task {}".format(subtaskId))

        response = lambda session: self.__connectionForResultRejectedFailure(session, connId, keyId, subtaskId)

        if keyId in self.responseList:
            self.responseList[keyId].append(response)
        else:
            self.responseList[keyId] = deque([response])

        self.client.wantToStartTaskSession(keyId, self.node, connId)

    #############################
    def __connectionForPayForTaskEstablished(self, session, connId, keyId, taskId, price):
        session.taskServer = self
        session.taskComputer = self.taskComputer
        session.taskManager = self.taskManager
        session.clientKeyId = keyId
        session.connId = connId
        self._markConnected(connId, session.address, session.port)
        session.sendHello()
        session.sendRewardForTask(taskId, price)
        self.client.taskRewardPaid(taskId, price)


    #############################
    def __connectionForPayForTaskFailure(self, connId, keyId, taskId, price):
        logger.warning("Cannot connect to pay for task {} ".format(taskId))
        self.client.taskRewardPaymentFailure(taskId, price)

        response = lambda session: self.__connectionForPayForTaskFailure(session, connId, keyId, taskId,
                                                                             price)

        if keyId in self.responseList:
            self.responseList[keyId].append(response)
        else:
            self.responseList[keyId] = deque([response])

        self.client.wantToStartTaskSession(keyId, self.node, connId)
        #TODO
        # Taka informacja powinna byc przechowywana i proba oplaty powinna byc wysylana po jakims czasie


    #############################
    def __connectionForStartSessionEstablished(self, session, connId, keyId, nodeInfo, superNodeInfo):
        session.taskServer = self
        session.taskManager = self.taskManager
        session.taskComputer = self.taskComputer
        session.clientKeyId = keyId
        session.connId = connId
        self._markConnected(connId, session.address, session.port)
        session.sendHello()
        session.sendStartSessionResponse(connId)

    #############################
    def __connectionForStartSessionFailure(self, connId, keyId, nodeInfo, superNodeInfo):
        logger.info("Failed to start requested task session for node {}".format(keyId))
        #TODO CO w takiej sytuacji?
        if superNodeInfo is None:
            logger.info("Permanently can't connect to node {}".format(keyId))
            return

        args = (superNodeInfo.key, nodeInfo, self.node, connId)
        self._addPendingRequest(TaskConnTypes.Middleman, superNodeInfo, superNodeInfo.prvPort,
                                superNodeInfo.key, args)

        #TODO Dodatkowe usuniecie tego zadania (bo zastapione innym)

    #############################
    def __connectionForMiddlemanEstablished(self, session, connId, keyId, askingNodeInfo, selfNodeInfo, askConnId):
        session.taskServer = self
        session.taskManager = self.taskManager
        session.taskComputer = self.taskComputer
        session.clientKeyId = keyId
        session.connId = connId
        session.sendHello()
        session.sendMiddleman(askingNodeInfo, selfNodeInfo, askConnId)

    #############################
    def __connectionForMiddlemanFailure(self, connId, keyId, askingNodeInfo, selfNodeInfo, askConnID):
        #TODO CO w takiej sytuacji? Usuniecie jakichs portow?
        logger.info("Permanently can't connect to node {}".format(keyId))
        return

    #############################
    def __askingNodeForMiddlemanConnectionEstablished(self, session, connId, keyId, openSession,  askingNode, destNode,
                                                      askConnId):
        session.taskServer = self
        session.taskManager = self.taskManager
        session.taskComputer = self.taskComputer
        session.clientKeyId = keyId
        session.connId = connId
        session.sendHello()
        session.sendJoinMiddlemanConn(keyId, askConnId, destNode.key)
        session.openSession = openSession
        openSession.openSession = session

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
            if curTime - session.lastMessageTime > self.lastMessageTimeThreshold:
                sessionsToRemove.append(subtaskId)
        for subtaskId in sessionsToRemove:
            if self.taskSessions[subtaskId].taskComputer is not None:
                self.taskSessions[subtaskId].taskComputer.sessionTimeout()
            self.taskSessions[subtaskId].dropped()

    #############################
    def __sendWaitingResults(self):
        for wtr in self.resultsToSend.itervalues():

            if not wtr.alreadySending:
                if time.time() - wtr.lastSendingTrial > wtr.delayTime:
                    wtr.alreadySending = True
                    args = (wtr.ownerKeyId, wtr)
                    self._addPendingRequest(TaskConnTypes.TaskResult, wtr.owner, wtr.ownerPort, wtr.ownerKeyId, args)

        for wtf in self.failuresToSend.itervalues():
            args = (wtf.ownerKeId, wtf.subtaskId, wtf.errMsg)
            self._addPendingRequest(TaskConnTypes.TaskFailure, wtf.owner, wtf.ownerPort, wtf.ownerKeyId, args)

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
    def _getHostInfos(self, nodeInfo, port, keyId):
        hostInfos = PendingConnectionsServer._getHostInfos(self, nodeInfo, port, keyId)
        addr = self.client.getSuggestedAddr(keyId)
        if addr:
            hostData = HostData(addr, port)
            if hostData in hostInfos:
                hostInfos.remove(hostData)
            hostInfos = [HostData(addr, port)] + hostInfos
        return hostInfos

    #############################
    def _setConnEstablished(self):
        self.connEstablishedForType.update({
            TaskConnTypes.TaskRequest: self.__connectionForTaskRequestEstablished,
            TaskConnTypes.PayForTask: self.__connectionForPayForTaskEstablished,
            TaskConnTypes.ResourceRequest: self.__connectionForResourceRequestEstablished,
            TaskConnTypes.ResultRejected: self.__connectionForResultRejectedEstablished,
            TaskConnTypes.TaskResult: self.__connectionForTaskResultEstablished,
            TaskConnTypes.TaskFailure: self.__connectionForTaskFailureEstablished,
            TaskConnTypes.StartSession: self.__connectionForStartSessionEstablished,
            TaskConnTypes.Middleman: self.__connectionForMiddlemanEstablished
        })

    #############################
    def _setConnFailure(self):
        self.connFailureForType.update({
            TaskConnTypes.TaskRequest: self.__connectionForTaskRequestFailure,
            TaskConnTypes.PayForTask: self.__connectionForPayForTaskFailure,
            TaskConnTypes.ResourceRequest: self.__connectionForResourceRequestFailure,
            TaskConnTypes.ResultRejected: self.__connectionForResultRejectedFailure,
            TaskConnTypes.TaskResult: self.__connectionForTaskResultFailure,
            TaskConnTypes.TaskFailure: self.__connectionForTaskFailureFailure,
            TaskConnTypes.StartSession: self.__connectionForStartSessionFailure,
            TaskConnTypes.Middleman: self.__connectionForMiddlemanFailure
        })

##########################################################

class WaitingTaskResult:
    #############################
    def __init__(self, subtaskId, result, resultType, lastSendingTrial, delayTime, ownerAddress, ownerPort, ownerKeyId,
                 owner):
        self.subtaskId          = subtaskId
        self.result             = result
        self.resultType         = resultType
        self.lastSendingTrial   = lastSendingTrial
        self.delayTime          = delayTime
        self.ownerAddress       = ownerAddress
        self.ownerPort          = ownerPort
        self.ownerKeyId         = ownerKeyId
        self.owner              = owner
        self.alreadySending     = False

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

from twisted.internet.protocol import Factory
from golem.network.NetAndFilesConnState import MidNetAndFilesConnState
from TaskSession import TaskSessionFactory

class TaskServerFactory(Factory):
    #############################
    def __init__(self, server):
        self.server = server

    #############################
    def buildProtocol(self, addr):
        logger.info("Protocol build for {}".format(addr))
        protocol = MidNetAndFilesConnState(self.server)
        protocol.setSessionFactory(TaskSessionFactory())
        return protocol

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


