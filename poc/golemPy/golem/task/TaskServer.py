import time
import os
import logging

from TaskManager import TaskManager
from TaskComputer import TaskComputer
from TaskSession import TaskSession
from TaskKeeper import TaskKeeper

from golem.network.transport.Tcp import Network, HostData
from golem.ranking.Ranking import RankingStats
from golem.core.hostaddress import getExternalAddress

logger = logging.getLogger(__name__)

class TaskServer:
    #############################
    def __init__(self, node, configDesc, keysAuth, client, useIp6=False):
        self.client             = client
        self.keysAuth           = keysAuth

        self.configDesc         = configDesc

        self.node               = node
        self.curPort            = configDesc.startPort
        self.taskKeeper         = TaskKeeper()
        self.taskManager        = TaskManager(configDesc.clientUid, self.node, keyId = self.keysAuth.getKeyId(), rootPath = self.__getTaskManagerRoot(configDesc), useDistributedResources = self.configDesc.useDistributedResourceManagement)
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
        self.__startAccepting()

    #############################
    def syncNetwork(self):
        self.taskComputer.run()
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
                self.__connectAndSendTaskRequest(self.configDesc.clientUid,
                                              theader.taskOwnerPort,
                                              theader.taskOwnerKeyId,
                                              theader.taskOwner,
                                              theader.taskId,
                                              self.configDesc.estimatedPerformance,
                                              self.configDesc.maxResourceSize,
                                              self.configDesc.maxMemorySize,
                                              self.configDesc.numCores)



                return theader.taskId

        return 0

    #############################
    def requestResource(self, subtaskId, resourceHeader, address, port, keyId, taskOwner):
        self.__connectAndSendResourceRequest(address, port, keyId, taskOwner, subtaskId, resourceHeader)
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
    def addResourcePeer(self, clientId, addr, port, keyId):
        self.client.addResourcePeer(clientId, addr, port, keyId)

    #############################
    def taskResultSent(self, subtaskId):
        if subtaskId in self.resultsToSend:
            del self.resultsToSend[subtaskId]
        else:
            assert False

    #############################
    def changeConfig(self, configDesc):
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
        self.__connectAndPayForTask(address, port, keyId, nodeInfo, taskId, price)

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

        self.__connectAndSendResultRejected(subtaskId, accountInfo.address, accountInfo.port, accountInfo.keyId,
                                            accountInfo.nodeInfo)

    ###########################
    def unpackDelta(self, destDir, delta, taskId):
        self.client.resourceServer.unpackDelta(destDir, delta, taskId)

    #############################
    def getComputingTrust(self, nodeId):
        return self.client.getComputingTrust(nodeId)

    #############################
    # PRIVATE SECTION
    #############################
    def __startAccepting(self):
        logger.info("Enabling tasks accepting state")
        Network.listen(self.configDesc.startPort, self.configDesc.endPort, TaskServerFactory(self), None, self.__listeningEstablished, self.__listeningFailure, self.useIp6)

    #############################
    def __listeningEstablished(self, iListeningPort):
        port = iListeningPort.getHost().port
        self.curPort = port
        logger.info("Port {} opened - listening".format(port))
        self.taskManager.listenAddress = self.node.prvAddr
        self.taskManager.listenPort = self.curPort
        self.taskManager.node = self.node

    #############################
    def __listeningFailure(self, p):
        self.curPort = 0
        logger.error("Task server not listening")
        #FIXME: some graceful terminations should take place here
        # sys.exit(0)

    #############################   
    def __connectAndSendTaskRequest(self, clientId, port, keyId, taskOwner, taskId,
                                    estimatedPerformance, maxResourceSize, maxMemorySize, numCores):

        #Test innej metody
        # Network.connect(address, port, TaskSession, self.__connectionForTaskRequestEstablished,
        #                 self.__connectionForTaskRequestFailure, clientId, keyId, taskId,
        #                 estimatedPerformance, maxResourceSize, maxMemorySize, numCores)
        hostInfos = [HostData(i, port) for i in taskOwner.prvAddresses]
        hostInfos.append(HostData(taskOwner.pubAddr, taskOwner.pubPort))
        Network.connectToHost(hostInfos, TaskSession, self.__connectionForTaskRequestEstablished,
                              self.__connectionForTaskRequestFailure, clientId, keyId, taskId, estimatedPerformance,
                              maxResourceSize, maxMemorySize, numCores)

    #############################   
    def __connectAndSendResourceRequest(self, address, port, keyId, taskOwner, subtaskId, resourceHeader):
        #Test Innej metody
        # Network.connect(address, port, TaskSession, self.__connectionForResourceRequestEstablished,
        #                 self.__connectionForResourceRequestFailure, keyId, subtaskId, resourceHeader)

        hostInfos = [HostData(i, port) for i in taskOwner.prvAddresses]
        hostInfos.append(HostData(taskOwner.pubAddr, taskOwner.pubPort))
        Network.connectToHost(hostInfos, TaskSession, self.__connectionForResourceRequestEstablished,
                              self.__connectionForResourceRequestFailure, keyId, subtaskId, resourceHeader)

    #############################
    def __connectAndSendResultRejected(self, subtaskId, address, port, keyId, taskOwner):
        #Test innej metody
        # Network.connect(address, port, TaskSession, self.__connectionForSendResultRejectedEstablished,
        #                 self.__connectionForResultRejectedFailure, keyId, subtaskId)
        hostInfos = [HostData(i, port) for i in taskOwner.prvAddresses]
        hostInfos.append(HostData(taskOwner.pubAddr, taskOwner.pubPort))
        Network.connectToHost(hostInfos, TaskSession, self.__connectionForSendResultRejectedEstablished,
                         self.__connectionForResultRejectedFailure, keyId, subtaskId)

    #############################
    def __connectAndPayForTask(self, address, port, keyId, taskOwner, taskId, price):
        #Test innej metody
        # Network.connect(address, port, TaskSession, self.__connectionForPayForTaskEstablished,
        #                 self.__connectionForPayForTaskFailure, keyId, taskId, price)
        hostInfos = [HostData(i, port) for i in taskOwner.prvAddresses]
        hostInfos.append(HostData(taskOwner.pubAddr, taskOwner.pubPort))
        Network.connectToHost(hostInfos, TaskSession, self.__connectionForPayForTaskEstablished,
                        self.__connectionForPayForTaskFailure, keyId, taskId, price)

    #############################
    def __connectionForTaskRequestEstablished(self, session, clientId, keyId, taskId, estimatedPerformance,
                                              maxResourceSize, maxMemorySize, numCores):

        session.taskId = taskId
        session.clientKeyId = keyId
        session.taskServer = self
        session.taskComputer = self.taskComputer
        session.taskManager = self.taskManager
        self.taskSessions[taskId] = session
        session.sendHello()
        session.requestTask(clientId, taskId, estimatedPerformance, maxResourceSize, maxMemorySize, numCores)

    #############################
    def __connectionForTaskRequestFailure(self, clientId, keyId, taskId, estimatedPerformance, *args):
        logger.warning("Cannot connect to task {} owner".format(taskId))
        logger.warning("Removing task {} from task list".format(taskId))

        self.taskComputer.taskRequestRejected(taskId, "Connection failed")
        self.taskKeeper.requestFailure(taskId)

    #############################   
    def __connectAndSendTaskResults(self, address, port, keyId, taskOwner, waitingTaskResult):
        #Test innej metody
        # Network.connect(address, port, TaskSession, self.__connectionForTaskResultEstablished,
        #                 self.__connectionForTaskResultFailure, keyId, waitingTaskResult)
        hostInfos = [HostData(i, port) for i in taskOwner.prvAddresses]
        hostInfos.append(HostData(taskOwner.pubAddr, taskOwner.pubPort))
        Network.connectToHost(hostInfos, TaskSession, self.__connectionForTaskResultEstablished,
                         self.__connectionForTaskResultFailure, keyId, waitingTaskResult)

    #############################
    def __connectAndSendTaskFailure(self, address, port, keyId, taskOwner, subtaskId, errMsg):
        #Test innej metody
        # Network.connect(address, port, TaskSession, self.__connectionForTaskFailureEstablished,
        #                 self.__connectionForTaskFailureFailure, keyId, subtaskId, errMsg)
        hostInfos = [HostData(i, port) for i in taskOwner.prvAddresses]
        hostInfos.append(HostData(taskOwner.pubAddr, taskOwner.pubPort))
        Network.connectToHost(hostInfos, TaskSession, self.__connectionForTaskFailureEstablished,
                              self.__connectionForTaskFailureFailure, keyId, subtaskId, errMsg)

    #############################
    def __connectionForTaskResultEstablished(self, session, keyId, waitingTaskResult):
        session.taskServer = self
        session.taskComputer = self.taskComputer
        session.taskManager = self.taskManager
        session.clientKeyId = keyId

        self.taskSessions[waitingTaskResult.subtaskId] = session

        session.sendHello()
        session.sendReportComputedTask(waitingTaskResult, self.node.prvAddr, self.curPort, self.client.getEthAccount(),
                                       self.node)

    #############################
    def __connectionForTaskResultFailure(self, keyId, waitingTaskResult):
        logger.warning("Cannot connect to task {} owner".format(waitingTaskResult.subtaskId))
        logger.warning("Removing task {} from task list".format(waitingTaskResult.subtaskId))
        
        waitingTaskResult.lastSendingTrial  = time.time()
        waitingTaskResult.delayTime         = self.configDesc.maxResultsSendingDelay
        waitingTaskResult.alreadySending    = False

    #############################
    def __connectionForTaskFailureEstablished(self, session, keyId, subtaskId, errMsg):
        session.taskServer = self
        session.clientKeyId = keyId
        self.taskSessions[subtaskId] = session
        session.sendHello()
        session.sendTaskFailure(subtaskId, errMsg)

    #############################
    def __connectionForTaskFailureFailure(self, keyId, subtaskId, errMsg):
        logger.warning("Cannot connect to task {} owner".format(subtaskId))

    #############################
    def __connectionForResourceRequestEstablished(self, session, keyId, subtaskId, resourceHeader):

        session.taskServer = self
        session.taskComputer = self.taskComputer
        session.taskManager = self.taskManager
        session.clientKeyId = keyId
        session.taskId = subtaskId
        self.taskSessions[subtaskId] = session
        session.sendHello()
        session.requestResource(subtaskId, resourceHeader)

    #############################
    def __connectionForResourceRequestFailure(self, session, keyId, subtaskId, resourceHeader):
        logger.warning("Cannot connect to task {} owner".format(subtaskId))
        logger.warning("Removing task {} from task list".format(subtaskId))
        
        self.taskComputer.resourceRequestRejected(subtaskId, "Connection failed")
        
        self.removeTaskHeader(subtaskId)

    #############################
    def __connectionForResultRejectedFailure(self, keyId, subtaskId):
        logger.warning("Cannot connect to deliver information about rejected result for task {}".format(subtaskId))

    #############################
    def __connectionForPayForTaskFailure(self, keyId, taskId, price):
        logger.warning("Cannot connect to pay for task {} ".format(taskId))
        self.client.taskRewardPaymentFailure(taskId, price)
        #TODO
        # Taka informacja powinna byc przechowywana i proba oplaty powinna byc wysylana po jakims czasie

    #############################
    def __connectionForSendResultRejectedEstablished(self, session, keyId, subtaskId):
        session.taskServer = self
        session.taskComputer = self.taskComputer
        session.taskManager = self.taskManager
        session.clientKeyId = keyId
        session.sendHello()
        session.sendResultRejected(subtaskId)

    #############################
    def __connectionForPayForTaskEstablished(self, session, keyId, taskId, price):
        session.taskServer = self
        session.taskComputer = self.taskComputer
        session.taskManager = self.taskManager
        session.clientKeyId = keyId
        session.sendHello()
        session.sendRewardForTask(taskId, price)
        self.client.taskRewardPaid(taskId, price)

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
        for wtr in self.resultsToSend:
            waitingTaskResult = self.resultsToSend[wtr]

            if not waitingTaskResult.alreadySending:
                if time.time() - waitingTaskResult.lastSendingTrial > waitingTaskResult.delayTime:
                    waitingTaskResult.alreadySending = True
                    self.__connectAndSendTaskResults(waitingTaskResult.ownerAddress, waitingTaskResult.ownerPort,
                                                     waitingTaskResult.ownerKeyId, waitingTaskResult.owner,
                                                     waitingTaskResult)

        for wtf in self.failuresToSend.itervalues():
            self.__connectAndSendTaskFailure(wtf.ownerAddress, wtf.ownerPort, wtf.ownerKeyId, wtf.owner,
                                             wtf.subtaskId, wtf.errMsg)
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

    #############################
    def __getTaskManagerRoot(self, configDesc):
        return os.path.join(configDesc.rootPath, "res")

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
from golem.network.NetAndFilesConnState import NetAndFilesConnState
from TaskSession import TaskSessionFactory

class TaskServerFactory(Factory):
    #############################
    def __init__(self, server):
        self.server = server

    #############################
    def buildProtocol(self, addr):
        logger.info("Protocol build for {}".format(addr))
        protocol = NetAndFilesConnState(self.server)
        protocol.setSessionFactory(TaskSessionFactory())
        return protocol