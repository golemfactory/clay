
from golem.Message import MessageWantToComputeTask, MessageTaskToCompute, MessageCannotAssignTask, MessageGetResource, MessageResource, MessageReportComputedTask, MessageTaskResult, MessageGetTaskResult, MessageRemoveTask, MessageSubtaskResultAccepted, MessageSubtaskResultRejected, MessageDeltaParts, MessageResourceFormat, MessageAcceptResourceFormat
from TaskConnState import TaskConnState
import time
import cPickle as pickle
import os
import struct
import logging

logger = logging.getLogger(__name__)

LONG_STANDARD_SIZE = 4

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

        self.recvSize = 0
        self.dataSize = -1
        self.lastPrct = 0
        self.locData = ""
        self.subtaskId = ""

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
                    result = pickle.dumps( res.result )
                    dataProducer = DataProducer( result, self, res.subtaskId)
                    res.alreadySending = True
#                    self.__send( MessageTaskResult( res.subtaskId, res.result ) )
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
                self.conn.fileMode = True
            self.__sendAcceptResourceFormat()

    ##########################
    def dropped( self ):
        self.conn.close()
        self.taskServer.removeTaskSession( self )

    ##########################
    def resultDataReceived(self, taskId, data, conn ):

        if self.dataSize == -1:
            self.__receiveFirstDataChunk( data )
        else:
            self.locData += data

        self.recvSize = len( self.locData )
        prct = int( 100 * self.recvSize / float( self.dataSize ) )
        if prct > self.lastPrct:
            print "\rFile data receving {} %                       ".format(  prct ),
            self.lastPrct = prct

        if self.recvSize == self.dataSize:
            conn.dataMode = False
            result = pickle.loads( self.locData )
            self.dataSize = -1
            self.recvSize = 0
            self.locData = ""
            self.__receiveTaskResult( self.subtaskId, result )

    ##########################
    def __receiveFirstDataChunk( self, data  ):
        self.lastPrct = 0
        ( self.dataSize, ) = struct.unpack( "!L", data[0:LONG_STANDARD_SIZE] )
        self.locData = data[ LONG_STANDARD_SIZE: ]

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

    def __receiveTaskResult(self, subtaskId, result ):
        self.taskManager.computedTaskReceived( subtaskId, result )
        if self.taskManager.verifySubtask( subtaskId ):
            reward = self.taskServer.payForTask( subtaskId )
            self.__send( MessageSubtaskResultAccepted( subtaskId, reward ) )
        else:
            self.__send( MessageSubtaskResultRejected( subtaskId ) )
        self.dropped()

class FileProducer:
    def __init__( self, file_, taskSession ):

        self.file_ = file_
        self.taskSession = taskSession
        self.paused = False
        self.openFile()
        self.register()

    def openFile( self ):
        self.fh = open( self.file_, 'rb' )
        self.size = os.path.getsize( self.file_ )
        logger.info( "Sendig file size:{}".format( self.size ) )
        self.data = struct.pack( "!L", self.size ) + self.fh.read( 1024 * 1024 )

    def register( self ):
        self.taskSession.conn.transport.registerProducer( self, False )

    def stopProducing( self ):
        self.paused = True

    def resumeProducing( self ):
        if self.data:
            self.taskSession.conn.transport.write( self.data )
            print "\rSending progress {} %                       ".format( int( 100 * float( self.fh.tell() ) / self.size ) ),
            self.data = self.fh.read( 1024 * 1024 )
        else:
            self.fh.close()
            self.taskSession.conn.transport.unregisterProducer()
            self.taskSession.dropped()


    def pauseProducing(self):
        self.paused = True

class DataProducer:
    def __init__( self, dataToSend, taskSession, subtaskId, buffSize = 1024 * 1024 * 1024 ):
        self.dataToSend = dataToSend
        self.taskSession = taskSession
        self.paused = False
        self.data = None
        self.it = 0
        self.numSend = 0
        self.subtaskId = subtaskId
        self.buffSize = buffSize
        self.loadData()
        self.register()

    def loadData( self ):
        self.size = len( self.dataToSend )
        logger.info( "Sendig file size:{}".format( self.size ) )
        self.data = struct.pack( "!L", self.size )
        dataLen = len( self.data )
        self.data += self.dataToSend[: self.buffSize ]
        self.it = self.buffSize
        self.size += LONG_STANDARD_SIZE

    def register( self ):
        self.taskSession.conn.transport.registerProducer( self, False )

    def resumeProducing( self ):
        if self.data:
            self.taskSession.conn.transport.write( self.data )
            self.numSend += len( self.data )
            print "\rSending progress {} %                       ".format( int( 100 * float( self.numSend ) / self.size ) ),
            if self.it < len( self.dataToSend ):
                self.data = self.dataToSend[self.it:self.it + self.buffSize]
                self.it += self.buffSize
            else:
                self.data = None
                self.taskSession.taskServer.taskResultSent( self.subtaskId )
                self.taskSession.conn.transport.unregisterProducer()
                self.taskSession.dropped()

    def stopProducing( self ):
        self.paused = True

    def pauseProducing( self ):
        self.paused = True
