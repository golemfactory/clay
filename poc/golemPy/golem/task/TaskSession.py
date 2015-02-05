import time
import cPickle as pickle
import struct
import logging
import os

from TaskConnState import TaskConnState
from golem.Message import MessageWantToComputeTask, MessageTaskToCompute, MessageCannotAssignTask, MessageGetResource, MessageResource, MessageReportComputedTask, MessageTaskResult, MessageGetTaskResult, MessageRemoveTask, MessageSubtaskResultAccepted, MessageSubtaskResultRejected, MessageDeltaParts, MessageResourceFormat, MessageAcceptResourceFormat
from golem.network.FileProducer import FileProducer
from golem.network.DataProducer import DataProducer
from golem.network.FileConsumer import FileConsumer
from golem.network.DataConsumer import DataConsumer
from golem.network.MultiFileProducer import MultiFileProducer
from golem.network.MultiFileConsumer import MultiFileConsumer
from golem.task.TaskBase import resultTypes

logger = logging.getLogger(__name__)

class TaskSession:

    ConnectionStateType = TaskConnState

    ##########################
    def __init__( self, conn ):
        self.conn           = conn
        self.taskServer     = None
        self.taskManager    = None
        self.taskComputer   = None
        self.address        = self.conn.transport.getPeer().host
        self.port           = self.conn.transport.getPeer().port
        self.taskId         = 0

        self.lastResourceMsg = None

    ##########################
    def requestTask( self, clientId, taskId, performenceIndex, maxResourceSize, maxMemorySize, numCores ):
        self.__send( MessageWantToComputeTask( clientId, taskId, performenceIndex, maxResourceSize, maxMemorySize, numCores ) )

    ##########################
    def requestResource( self, taskId, resourceHeader ):
        self.__send( MessageGetResource( taskId, pickle.dumps( resourceHeader ) ) )

    ##########################
    def sendReportComputedTask( self, taskResult ):
        if taskResult.resultType == resultTypes['data']:
            extraData = []
        elif taskResult.resultType == resultTypes['files']:
            extraData = [ os.path.basename(x) for x in taskResult.result ]
        else:
            logger.error("Unknown result type {}".format( taskResult.resultType ) )
            return

        self.__send( MessageReportComputedTask( taskResult.subtaskId, taskResult.resultType, extraData ) )

    ##########################
    def interpret( self, msg ):
        if msg is None:
            return

        #print "Receiving from {}:{}: {}".format( self.address, self.port, msg )

        self.taskServer.setLastMessage( "<-", time.localtime(), msg, self.address, self.port )

        type = msg.getType()

        #localtime   = time.localtime()
        #timeString  = time.strftime("%H:%M:%S", localtime)
        #print "{} at {}".format( msg.serialize(), timeString )

        if type == MessageWantToComputeTask.Type:

            ctd, wrongTask = self.taskManager.getNextSubTask( msg.clientId, msg.taskId, msg.perfIndex, msg.maxResourceSize, msg.maxMemorySize, msg.numCores )

            if wrongTask:
                self.conn.sendMessage( MessageCannotAssignTask( msg.taskId, "Not my task  {}".format( msg.taskId ) ) )
                self.conn.sendMessage( MessageRemoveTask( msg.taskId ) )
            elif ctd:
                self.conn.sendMessage( MessageTaskToCompute( ctd ) )
            else:
                self.conn.sendMessage( MessageCannotAssignTask( msg.taskId, "No more subtasks in {}".format( msg.taskId ) ) )

        elif type == MessageTaskToCompute.Type:
            self.taskComputer.taskGiven(  msg.ctd )
            self.dropped()

        elif type == MessageCannotAssignTask.Type:
            self.taskComputer.taskRequestRejected( msg.taskId, msg.reason )
            self.taskServer.removeTaskHeader( msg.taskId )
            self.dropped()

        elif type == MessageReportComputedTask.Type:
            if msg.subtaskId in self.taskManager.subTask2TaskMapping:
                delay = self.taskManager.acceptResultsDelay( self.taskManager.subTask2TaskMapping[ msg.subtaskId ] )

                if delay == -1.0:
                    self.dropped()
                elif delay == 0.0:
                    self.conn.sendMessage( MessageGetTaskResult( msg.subtaskId, delay ) )

                    if msg.resultType == resultTypes['data']:
                        self.__receiveDataResult( msg )
                    elif msg.resultType == resultTypes['files']:
                        self.__receiveFilesResult( msg)
                    else:
                        logger.error("Unknown result type {}".format( msg.resultType ) )
                        self.dropped()
                else:
                    self.conn.sendMessage( MessageGetTaskResult( msg.subtaskId, delay ) )
                    self.dropped()
            else:
                self.dropped()

        elif type == MessageGetTaskResult.Type:
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

        elif type == MessageTaskResult.Type:
           self.__receiveTaskResult( msg.subtaskId, msg.result )
        elif type == MessageGetResource.Type:
            self.lastResourceMsg = msg
            self.__sendResourceFormat ( self.taskServer.configDesc.useDistributedResourceManagement )
        elif type == MessageAcceptResourceFormat.Type:
            if self.lastResourceMsg is not None:
                if self.taskServer.configDesc.useDistributedResourceManagement:
                    self.__sendResourcePartsList( self.lastResourceMsg )
                else:
                    self.__sendDeltaResource( self.lastResourceMsg )
                self.lastResourceMsg = None
            else:
                logger.error("Unexpected MessageAcceptResource message")
                self.dropped()
        elif type == MessageResource.Type:
            self.taskComputer.resourceGiven( msg.subtaskId )
            self.dropped()
        elif type == MessageSubtaskResultAccepted.Type:
            self.taskServer.subtaskAccepted( msg.subtaskId, msg.reward )
        elif type == MessageSubtaskResultRejected.Type:
            self.taskServer.subtaskRejected( msg.subtaskId )
        elif type == MessageDeltaParts.Type:
            self.taskComputer.waitForResources( self.taskId, msg.deltaHeader )
            self.taskServer.pullResources( self.taskId, msg.parts )
            self.dropped()
        elif type == MessageResourceFormat.Type:
            if not msg.useDistributedResource:
                tmpFile = os.path.join( self.taskComputer.resourceManager.getTemporaryDir( self.taskId ), "res" + self.taskId )
                outputDir = self.taskComputer.resourceManager.getResourceDir( self.taskId )
                extraData = { "taskId": self.taskId }
                self.conn.fileConsumer = FileConsumer( tmpFile, outputDir, self, extraData )
                self.conn.fileMode = True
            self.__sendAcceptResourceFormat()

    ##########################
    def dropped( self ):
        self.conn.close()
        self.taskServer.removeTaskSession( self )

    ##########################
    def fileSent( self, file_ ):
        self.dropped()

    ##########################
    def dataSent(self, extraData ):
        if 'subtaskId' in extraData:
            self.taskServer.taskResultSent( extraData['subtaskId'] )
        else:
            logger.error( "No subtaskId in extraData for sent data" )
        self.dropped()

    ##########################
    def fullFileReceived( self, extraData ):
        if 'taskId' in extraData:
            self.taskComputer.resourceGiven( extraData['taskId'] )
        else:
            logger.error( "No taskId in extraData for received File")
        self.dropped()


    ##########################
    def __send( self, msg ):
        #print "Sending to {}:{}: {}".format( self.address, self.port, msg )
        self.conn.sendMessage( msg )
        self.taskServer.setLastMessage( "->", time.localtime(), msg, self.address, self.port )

    ##########################
    def __sendDeltaResource(self, msg ):
        resFilePath = self.taskManager.prepareResource( msg.taskId, pickle.loads( msg.resourceHeader ) )
        #resFilePath  = "d:/src/golem/poc/golemPy/test/res2222221"

        if not resFilePath:
            logger.error( "Task {} has no resource".format( msg.taskId ) )
            self.conn.transport.write( struct.pack( "!L", 0 ) )
            self.dropped()
            return

        producer = FileProducer( resFilePath, self )

        #Producer powinien zakonczyc tu polaczenie
        #self.dropped()

    ##########################
    def __sendResourcePartsList(self, msg ):
        deltaHeader, partsList = self.taskManager.getResourcePartsList( msg.taskId, pickle.loads( msg.resourceHeader ) )
        self.__send( MessageDeltaParts( self.taskId, deltaHeader, partsList ) )

    ##########################
    def __sendResourceFormat( self, useDistributedResource ):
        self.__send( MessageResourceFormat( useDistributedResource ) )

    ##########################
    def __sendAcceptResourceFormat( self ):
        self.__send( MessageAcceptResourceFormat() )

    ##########################
    def __sendDataResults( self, res ):
        result = pickle.dumps( res.result )
        extraData = { 'subtaskId': res.subtaskId }
        dataProducer = DataProducer( result, self, extraData = extraData )

    def __sendFilesResults( self, res ):
        extraData = { 'subtaskId': res.subtaskId }
        multiFileProducer = MultiFileProducer( res.result, self, extraData = extraData )

    ##########################
    def __receiveDataResult( self, msg ):
        extraData = {"subtaskId": msg.subtaskId, "resultType": msg.resultType }
        self.conn.dataConsumer = DataConsumer( self, extraData )
        self.conn.dataMode = True
        self.subtaskId = msg.subtaskId

    def __receiveFilesResult( self, msg ):
        extraData = { "subtaskId": msg.subtaskId, "resultType": msg.resultType }
        outputDir = self.taskServer.taskManager.dirManager.getTaskTemporaryDir( self.taskManager.getTaskId( msg.subtaskId ), create = False )
        self.conn.dataConsumer = MultiFileConsumer( msg.extraData, outputDir, self, extraData )
        self.conn.dataMode = True
        self.subtaskId = msg.subtaskId

    ##########################
    def fullDataReceived(self, result, extraData ):
        if "resultType" not in extraData:
            logger.error( "No information about resultType for received data " )
            self.dropped()
            return

        if extraData['resultType'] == resultTypes['data']:
            try:
                result = pickle.loads( result )
            except Exception, err:
                logger.error( "Can't unpickle result data {}".format( str( err ) ) )

        if 'subtaskId' in extraData:
            subtaskId = extraData[ 'subtaskId' ]

            self.taskManager.computedTaskReceived( subtaskId, result, extraData['resultType'] )
            if self.taskManager.verifySubtask( subtaskId ):
                reward = self.taskServer.payForTask( subtaskId )
                self.__send( MessageSubtaskResultAccepted( subtaskId, reward ) )
            else:
                self.__send( MessageSubtaskResultRejected( subtaskId ) )
        else:
            logger.error("No taskId value in extraData for received data ")
        self.dropped()
