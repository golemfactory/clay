import time
import cPickle as pickle
import struct
import logging
import os

from TaskConnState import TaskConnState
from golem.Message import Message, MessageWantToComputeTask, MessageTaskToCompute, MessageCannotAssignTask, MessageGetResource, MessageResource, MessageReportComputedTask, MessageTaskResult, MessageGetTaskResult, MessageRemoveTask, MessageSubtaskResultAccepted, MessageSubtaskResultRejected, MessageDeltaParts, MessageResourceFormat, MessageAcceptResourceFormat, MessageTaskFailure
from golem.network.FileProducer import FileProducer
from golem.network.DataProducer import DataProducer
from golem.network.FileConsumer import FileConsumer
from golem.network.DataConsumer import DataConsumer
from golem.network.MultiFileProducer import MultiFileProducer
from golem.network.MultiFileConsumer import MultiFileConsumer
from golem.network.p2p.Session import NetSession
from golem.task.TaskBase import resultTypes

logger = logging.getLogger(__name__)

class TaskSession(NetSession):

    ConnectionStateType = TaskConnState

    ##########################
    def __init__(self, conn):
        NetSession.__init__(self, conn)
        self.taskServer     = None
        self.taskManager    = None
        self.taskComputer   = None
        self.taskId         = 0

        self.lastResourceMsg = None

        self.taskResultOwnerAddr = None
        self.taskResultOwnerPort = None
        self.taskResultOwnerNodeId = None
        self.taskResultOwnerEthAccount = None

        self.producer = None

        self.__setMsgInterpretations()

    ##########################
    def requestTask( self, clientId, taskId, performenceIndex, maxResourceSize, maxMemorySize, numCores ):
        self._send(MessageWantToComputeTask( clientId, taskId, performenceIndex, maxResourceSize, maxMemorySize, numCores))

    ##########################
    def requestResource( self, taskId, resourceHeader ):
        self._send( MessageGetResource( taskId, pickle.dumps( resourceHeader ) ) )

    ##########################
    def sendReportComputedTask( self, taskResult, address, port, ethAccount ):
        if taskResult.resultType == resultTypes['data']:
            extraData = []
        elif taskResult.resultType == resultTypes['files']:
            extraData = [ os.path.basename(x) for x in taskResult.result ]
        else:
            logger.error("Unknown result type {}".format( taskResult.resultType ) )
            return
        nodeId = self.taskServer.getClientId()

        self._send( MessageReportComputedTask( taskResult.subtaskId, taskResult.resultType, nodeId, address, port, ethAccount, extraData ) )

    ##########################
    def sendResultRejected( self, subtaskId ):
        self._send( MessageSubtaskResultRejected( subtaskId ))

    ##########################
    def sendRewardForTask( self, subtaskId, reward ):
        self._send( MessageSubtaskResultAccepted( subtaskId, reward ) )

    ##########################
    def sendTaskFailure(self, subtaskId, errMsg):
        self._send(MessageTaskFailure(subtaskId, errMsg))

    ##########################
    def interpret(self, msg):
      #  print "Receiving from {}:{}: {}".format( self.address, self.port, msg )

        self.taskServer.setLastMessage("<-", time.localtime(), msg, self.address, self.port)

        NetSession.interpret(self, msg)

        #localtime   = time.localtime()
        #timeString  = time.strftime("%H:%M:%S", localtime)
        #print "{} at {}".format( msg.serialize(), timeString )

    ##########################
    def dropped(self):
        self.clean()
        self.conn.clean()
        self.conn.close()
        if self.taskServer:
            self.taskServer.removeTaskSession(self)

    ##########################
    def clean(self):
        if self.producer is not None:
            self.producer.clean()

    ##########################
    def fileSent(self, file_):
        self.dropped()

    ##########################
    def dataSent(self, extraData):
        if 'subtaskId' in extraData:
            self.taskServer.taskResultSent(extraData['subtaskId'])
        else:
            logger.error("No subtaskId in extraData for sent data")
        self.producer = None
        self.dropped()

    ##########################
    def fullFileReceived(self, extraData):
        if 'taskId' in extraData:
            self.taskComputer.resourceGiven( extraData['taskId'] )
        else:
            logger.error( "No taskId in extraData for received File")
        self.producer = None
        self.dropped()

    ##########################
    def fullDataReceived(self, result, extraData):
        resultType = extraData.get('resultType')
        if resultType is None:
            logger.error( "No information about resultType for received data " )
            self.dropped()
            return

        if resultType == resultTypes['data']:
            try:
                result = pickle.loads( result )
            except Exception, err:
                logger.error( "Can't unpickle result data {}".format( str( err ) ) )

        subtaskId = extraData.get('subtaskId')
        if subtaskId:
            self.taskManager.computedTaskReceived( subtaskId, result, resultType )
            if self.taskManager.verifySubtask( subtaskId ):
                self.taskServer.acceptTask( subtaskId, self.taskResultOwnerAddr, self.taskResultOwnerPort, self.taskResultOwnerEthAccount )
            else:
                self.taskServer.rejectResult( subtaskId, self.taskResultOwnerNodeId, self.taskResultOwnerAddr, self.taskResultOwnerPort )
        else:
            logger.error("No taskId value in extraData for received data ")
        self.dropped()

    ##########################
    def _reactToWantToComputeTask(self, msg):
        trust = self.taskServer.getComputingTrust(msg.clientId)
        logger.debug("Computing trust level: {}".format(trust))
        if trust >= self.taskServer.configDesc.computingTrust:
            ctd, wrongTask = self.taskManager.getNextSubTask(msg.clientId, msg.taskId, msg.perfIndex, msg.maxResourceSize, msg.maxMemorySize, msg.numCores)
        else:
            ctd, wrongTask = None, False

        if wrongTask:
            self._send(MessageCannotAssignTask(msg.taskId, "Not my task  {}".format(msg.taskId)))
            self._send(MessageRemoveTask(msg.taskId))
        elif ctd:
            self._send(MessageTaskToCompute(ctd))
        else:
            self._send(MessageCannotAssignTask(msg.taskId, "No more subtasks in {}".format(msg.taskId)))

    ##########################
    def _reactToTaskToCompute(self, msg):
        self.taskComputer.taskGiven(msg.ctd, self.taskServer.getSubtaskTtl(msg.ctd.taskId))
        self.dropped()

    ##########################
    def _reactToCannotAssignTask(self, msg):
        self.taskComputer.taskRequestRejected( msg.taskId, msg.reason )
        self.taskServer.removeTaskHeader( msg.taskId )
        self.dropped()

    ##########################
    def _reactToReportComputedTask(self, msg):
        if msg.subtaskId in self.taskManager.subTask2TaskMapping:
            delay = self.taskManager.acceptResultsDelay( self.taskManager.subTask2TaskMapping[ msg.subtaskId ] )

            if delay == -1.0:
                self.dropped()
            elif delay == 0.0:
                self._send( MessageGetTaskResult( msg.subtaskId, delay ) )
                self.taskResultOwnerNodeId = msg.nodeId
                self.taskResultOwnerAddr = msg.address
                self.taskResultOwnerPort = msg.port
                self.taskResultOwnerEthAccount = msg.ethAccount

                if msg.resultType == resultTypes['data']:
                    self.__receiveDataResult( msg )
                elif msg.resultType == resultTypes['files']:
                    self.__receiveFilesResult( msg )
                else:
                    logger.error("Unknown result type {}".format( msg.resultType ) )
                    self.dropped()
            else:
                self._send( MessageGetTaskResult( msg.subtaskId, delay ) )
                self.dropped()
        else:
            self.dropped()

    ##########################
    def _reactToGetTaskResult(self, msg):
        res = self.taskServer.getWaitingTaskResult( msg.subtaskId )
        if res:
            if msg.delay == 0.0:
                res.alreadySending = True
                if res.resultType == resultTypes['data']:
                    self.__sendDataResults( res )
                elif res.resultType == resultTypes['files']:
                    self.__sendFilesResults( res )
                else:
                    logger.error( "Unknown result type {}".format( res.resultType ) )
                    self.dropped()
            else:
                res.lastSendingTrial    = time()
                res.delayTime           = msg.delay
                res.alreadySending      = False
                self.dropped()

    ##########################
    def _reactToTaskResult(self, msg):
        self.__receiveTaskResult( msg.subtaskId, msg.result )

    ##########################
    def _reactToGetResource(self, msg):
        self.lastResourceMsg = msg
        self.__sendResourceFormat ( self.taskServer.configDesc.useDistributedResourceManagement )

    ##########################
    def _reactToAcceptResourceFormat(self, msg):
        if self.lastResourceMsg is not None:
            if self.taskServer.configDesc.useDistributedResourceManagement:
                self.__sendResourcePartsList(self.lastResourceMsg)
            else:
                self.__sendDeltaResource(self.lastResourceMsg)
            self.lastResourceMsg = None
        else:
            logger.error("Unexpected MessageAcceptResource message")
            self.dropped()

    ##########################
    def _reactToResource(self, msg):
        self.taskComputer.resourceGiven(msg.subtaskId)
        self.dropped()

    ##########################
    def _reactToSubtaskResultAccepted(self, msg):
        self.taskServer.subtaskAccepted(msg.subtaskId, msg.reward)
        self.dropped()

    ##########################
    def _reactToSubtaskResultRejected(self, msg):
        self.taskServer.subtaskRejected(msg.subtaskId)
        self.dropped()

    ##########################
    def _reactToTaskFailure(self, msg):
        self.taskServer.subtaskFailure(msg.subtaskId, msg.err)
        self.dropped()

    ##########################
    def _reactToDeltaParts(self, msg):
        self.taskComputer.waitForResources(self.taskId, msg.deltaHeader)
        self.taskServer.pullResources(self.taskId, msg.parts)
        self.taskServer.addResourcePeer(msg.clientId, msg.addr, msg.port)
        self.dropped()

    ##########################
    def _reactToResourceFormat(self, msg):
        if not msg.useDistributedResource:
            tmpFile = os.path.join(self.taskComputer.resourceManager.getTemporaryDir(self.taskId), "res" + self.taskId)
            outputDir = self.taskComputer.resourceManager.getResourceDir(self.taskId)
            extraData = { "taskId": self.taskId }
            self.conn.fileConsumer = FileConsumer(tmpFile, outputDir, self, extraData)
            self.conn.fileMode = True
        self.__sendAcceptResourceFormat()

    ##########################
    def _send(self, msg):
        NetSession._send(self, msg, sendUnverified = True) #FIXME
       # print "Task Session Sending to {}:{}: {}".format( self.address, self.port, msg )
        self.taskServer.setLastMessage("->", time.localtime(), msg, self.address, self.port)

    ##########################
    def __sendDeltaResource(self, msg):
        resFilePath = self.taskManager.prepareResource( msg.taskId, pickle.loads( msg.resourceHeader ) )

        if not resFilePath:
            logger.error( "Task {} has no resource".format( msg.taskId ) )
            self.conn.transport.write( struct.pack( "!L", 0 ) )
            self.dropped()
            return

        self.producer = FileProducer( resFilePath, self )

    ##########################
    def __sendResourcePartsList(self, msg):
        deltaHeader, partsList = self.taskManager.getResourcePartsList( msg.taskId, pickle.loads( msg.resourceHeader ) )
        self._send(MessageDeltaParts(self.taskId, deltaHeader, partsList, self.taskServer.getClientId(), self.taskServer.getResourceAddr(), self.taskServer.getResourcePort()))

    ##########################
    def __sendResourceFormat(self, useDistributedResource):
        self._send(MessageResourceFormat(useDistributedResource))

    ##########################
    def __sendAcceptResourceFormat(self):
        self._send(MessageAcceptResourceFormat())

    ##########################
    def __sendDataResults(self, res):
        result = pickle.dumps(res.result)
        extraData = { 'subtaskId': res.subtaskId }
        self.producer = DataProducer(result, self, extraData = extraData)

    ##########################
    def __sendFilesResults(self, res):
        extraData = { 'subtaskId': res.subtaskId }
        self.producer = MultiFileProducer(res.result, self, extraData = extraData)

    ##########################
    def __receiveDataResult(self, msg):
        extraData = {"subtaskId": msg.subtaskId, "resultType": msg.resultType}
        self.conn.dataConsumer = DataConsumer(self, extraData)
        self.conn.dataMode = True
        self.subtaskId = msg.subtaskId

    ##########################
    def __receiveFilesResult(self, msg):
        extraData = { "subtaskId": msg.subtaskId, "resultType": msg.resultType }
        outputDir = self.taskServer.taskManager.dirManager.getTaskTemporaryDir(self.taskManager.getTaskId( msg.subtaskId ), create=False)
        self.conn.dataConsumer = MultiFileConsumer(msg.extraData, outputDir, self, extraData)
        self.conn.dataMode = True
        self.subtaskId = msg.subtaskId

    ##########################
    def __setMsgInterpretations(self):
        self.interpretation.update( {
                                MessageWantToComputeTask.Type: self._reactToWantToComputeTask,
                                MessageTaskToCompute.Type: self._reactToTaskToCompute,
                                MessageCannotAssignTask.Type: self._reactToCannotAssignTask,
                                MessageReportComputedTask.Type: self._reactToReportComputedTask,
                                MessageGetTaskResult.Type: self._reactToGetTaskResult,
                                MessageTaskResult.Type: self._reactToTaskResult,
                                MessageGetResource.Type: self._reactToGetResource,
                                MessageAcceptResourceFormat.Type: self._reactToAcceptResourceFormat,
                                MessageResource: self._reactToResource,
                                MessageSubtaskResultAccepted: self._reactToSubtaskResultAccepted,
                                MessageSubtaskResultRejected.Type: self._reactToSubtaskResultRejected,
                                MessageTaskFailure.Type: self._reactToTaskFailure,
                                MessageDeltaParts.Type: self._reactToDeltaParts,
                                MessageResourceFormat.Type: self._reactToResourceFormat
                            })


        self.canBeNotEncrypted.extend(self.interpretation.keys()) #FIXME
        self.canBeUnsigned.extend(self.interpretation.keys()) #FIXME
        self.canBeUnverified.extend(self.interpretation.keys()) #FIXME

##############################################################################

class TaskSessionFactory:
    def getSession(self, connection):
        return TaskSession(connection)