
from golem.Message import MessageWantToComputeTask, MessageTaskToCompute, MessageCannotAssignTask, MessageGetResource, MessageResource, MessageReportComputedTask, MessageTaskResult, MessageGetTaskResult, MessageRemoveTask, MessageSubtaskResultAccepted, MessageSubtaskResultRejected
from TaskConnState import TaskConnState
import time
import cPickle as pickle
import os
import struct
import logging

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

    ##########################
    def requestTask( self, clientId, taskId, performenceIndex, maxResourceSize, maxMemorySize, numCores ):
        self.__send( MessageWantToComputeTask( clientId, taskId, performenceIndex, maxResourceSize, maxMemorySize, numCores ) )

    ##########################
    def requestResource( self, taskId, resourceHeader ):
        self.__send( MessageGetResource( taskId, pickle.dumps( resourceHeader ) ) )
        self.conn.fileMode = True

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
                else:
                    self.conn.sendMessage( MessageGetTaskResult( msg.subtaskId, delay ) )
                    self.dropped()
            else:
                self.dropped()

        elif type == MessageGetTaskResult.Type:
            res = self.taskServer.getWaitingTaskResult( msg.subtaskId )
            if res:
                if msg.delay == 0.0:
                    self.__send( MessageTaskResult( res.subtaskId, res.result ) )
                    self.taskServer.taskResultSent( res.subtaskId )
                else:
                    res.lastSendingTrial    = time()
                    res.delayTime           = msg.delay
                    res.alreadySending      = False
                    self.dropped()

        elif type == MessageTaskResult.Type:
            self.taskManager.computedTaskReceived( msg.subtaskId, msg.result )
            if self.taskManager.verifySubtask( msg.subtaskId ):
                reward = self.taskServer.payForTask( msg.subtaskId )
                self.__send( MessageSubtaskResultAccepted( msg.subtaskId, reward ) )
            else:
                self.__send( MessageSubtaskResultRejected( msg.subtaskId ) )
            self.dropped()

        elif type == MessageGetResource.Type:
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
        elif type == MessageResource.Type:
            self.taskComputer.resourceGiven( msg.subtaskId )
            self.dropped()
        elif type == MessageSubtaskResultAccepted.Type:
            self.taskServer.subtaskAccepted( msg.subtaskId, msg.reward )
        elif type == MessageSubtaskResultRejected.Type:
            self.taskServer.subtaskRejected( msg.subtaskId )

    ##########################
    def dropped( self ):
        self.conn.close()
        self.taskServer.removeTaskSession( self )

    def __send( self, msg ):
        #print "Sending to {}:{}: {}".format( self.address, self.port, msg )
        self.conn.sendMessage( msg )
        self.taskServer.setLastMessage( "->", time.localtime(), msg, self.address, self.port )

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

