from computeconnstate import ComputeConnState
from message import MessageWantToComputeTask, MessageTaskToCompute, MessageCannotAssignTask, MessageTaskComputed
import time

class ComputeSession:

    ##########################
    def __init__( self, conn, server, address, port ):
        self.conn = conn
        self.server = server
        self.address = address
        self.port = port

    ##########################
    def start( self ):
        pass

    ##########################
    def askForTask( self, taskId, performenceIndex ):
        self.conn.sendMessage( MessageWantToComputeTask( taskId, performenceIndex ) )

    def sendComputedTask( self, id, extraData, taskResult ):
        self.conn.sendMessage( MessageTaskComputed( id, extraData, taskResult ) )

    ##########################
    def interpret( self, msg ):
        if msg is None:
            pass #TODO

        type = msg.getType()

        localtime   = time.localtime()
        timeString  = time.strftime("%H:%M:%S", localtime)
        print "{} at {}".format( msg.serialize(), timeString )

        if type == MessageWantToComputeTask.Type:
            tmsg = self.server.taskManager.giveTask( msg.taskId, msg.perfIndex )
            self.conn.sendMessage( tmsg )
        elif type == MessageTaskToCompute.Type:
            self.server.taskManager.taskToComputeReceived( msg )
        elif type == MessageCannotAssignTask.Type:
            self.server.taskManager.stopAsking( msg.id, msg.reason )
        elif type == MessageTaskComputed.Type:
            self.server.taskManager.receivedComputedTask( msg.id, msg.extraData, msg.result )

    def dropped( self ):
        self.conn.close()
        self.server.removeComputeSession( self )