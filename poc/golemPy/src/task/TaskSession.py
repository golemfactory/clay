
from Message import MessageWantToComputeTask, MessageTaskToCompute, MessageCannotAssignTask, MessageTaskComputed, MessageGetResource, MessageResource
from TaskComputer import TaskComputer
from TaskConnState import TaskConnState
import time
import cPickle as pickle
import Compress
import os
import struct

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
    def requestTask( self, taskId, performenceIndex ):
        self.__send( MessageWantToComputeTask( taskId, performenceIndex ) )

    ##########################
    def requestResource( self, taskId, resourceHeader ):
        self.__send( MessageGetResource( taskId, pickle.dumps( resourceHeader ) ) )
        self.taskId = taskId
        self.conn.fileMode = True

    ##########################
    def sendTaskResults( self, id, extraData, taskResult ):
        self.__send( MessageTaskComputed( id, extraData, taskResult ) )

    ##########################
    def interpret( self, msg ):
        if msg is None:
            pass #TODO

        #print "Receiving from {}:{}: {}".format( self.address, self.port, msg )

        self.taskServer.setLastMessage( "<-", time.localtime(), msg, self.address, self.port )

        type = msg.getType()

        #localtime   = time.localtime()
        #timeString  = time.strftime("%H:%M:%S", localtime)
        #print "{} at {}".format( msg.serialize(), timeString )

        if type == MessageWantToComputeTask.Type:

            taskId, srcCode, extraData, shortDescr = self.taskManager.getNextSubTask( msg.taskId, msg.perfIndex )

            if taskId != 0:
                self.conn.sendMessage( MessageTaskToCompute( taskId, extraData, shortDescr, srcCode ) )
            else:
                self.conn.sendMessage( MessageCannotAssignTask( msg.taskId, "No more subtasks in {}".format( msg.taskId ) ) )

        elif type == MessageTaskToCompute.Type:
            self.taskComputer.taskGiven( msg.taskId, msg.sourceCode, msg.extraData, msg.shortDescr )
            self.dropped()

        elif type == MessageCannotAssignTask.Type:
            self.taskComputer.taskRequestRejected( msg.taskId, msg.reason )
            self.taskServer.removeTaskHeader( msg.taskId )
            self.dropped()

        elif type == MessageTaskComputed.Type:
            self.taskServer.taskManager.computedTaskReceived( msg.id, msg.extraData, msg.result )
            # Add message with confirmation that result is accepted
            self.dropped()

        elif type == MessageGetResource.Type:
            resFilePath = self.taskManager.prepareResource( msg.taskId, pickle.loads( msg.resourceHeader ) )
            #resFilePath  = "d:/src/golem/poc/golemPy/test/res2222221"

            size = os.path.getsize( resFilePath )

            print "Sendig file size:{}".format( size )

            fh = open( resFilePath )
            self.conn.transport.write( struct.pack( "!L", size ) )
            data = fh.read( 1024 )
            while data:
                self.conn.transport.write( data )
                self.conn.transport.doWrite()
                print "\rSending progress {}                        ".format( float( fh.tell() ) / size ),
                data = fh.read( 1024 )
                
            print "CHUJA"
            #self.conn.sendMessage( MessageResource( msg.taskId, resDump ) )
            self.dropped()
        elif type == MessageResource.Type:
            res = Compress.decompress( msg.resource )
            res = pickle.loads( res )
            self.taskComputer.resourceGiven( self.taskId, res )
            self.dropped()

    ##########################
    def dropped( self ):
        self.conn.close()
        self.taskServer.removeTaskSession( self )

    def __send( self, msg ):
        #print "Sending to {}:{}: {}".format( self.address, self.port, msg )
        self.conn.sendMessage( msg )
        self.taskServer.setLastMessage( "->", time.localtime(), msg, self.address, self.port )