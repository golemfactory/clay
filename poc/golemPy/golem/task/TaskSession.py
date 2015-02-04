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
    def sendReportComputedTask( self, subtaskId ):
        self.__send( MessageReportComputedTask( subtaskId ) )

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
                    extraData = {"subtaskId": msg.subtaskId }
                    self.conn.dataConsumer = DataConsumer( self, extraData )
                    self.conn.dataMode = True
                    self.subtaskId = msg.subtaskId
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
        #            self.__send( MessageTaskResult( res.subtaskId, res.result ) )
                    result = pickle.dumps( res.result )
                    extraData = { 'subtaskId': res.subtaskId }
                    dataProducer = DataProducer( result, self, extraData = extraData )
#                    self.taskServer.taskResultSent( res.subtaskId )
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

    def __sendResourceFormat( self, useDistributedResource ):
        self.__send( MessageResourceFormat( useDistributedResource ) )

    def __sendAcceptResourceFormat( self ):
        self.__send( MessageAcceptResourceFormat() )

    def fullDataReceived(self, result, extraData ):
        try:
            result = pickle.loads( result )
        except Exception, err:
            logger.error( "Can't unpickle result data {}".format( str( err ) ) )
        if 'subtaskId' in extraData:
            subtaskId = extraData[ 'subtaskId' ]

            self.taskManager.computedTaskReceived( subtaskId, result )
            if self.taskManager.verifySubtask( subtaskId ):
                reward = self.taskServer.payForTask( subtaskId )
                self.__send( MessageSubtaskResultAccepted( subtaskId, reward ) )
            else:
                self.__send( MessageSubtaskResultRejected( subtaskId ) )
        else:
            logger.error("No taskId value in extraData for received data ")
        self.dropped()


