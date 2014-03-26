from computeconnstate import ComputeConnState
from message import MessageWantToComputeTask, MessageTaskToCompute
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

    ##########################
    def interpret( self, msg ):
        if msg is None:
            pass #TODO

        type = msg.getType()

        localtime   = time.localtime()
        timeString  = time.strftime("%H:%M:%S", localtime)
        print "{} at {}".format( msg.serialize(), timeString )

        if type == MessageWantToComputeTask.Type:
            pass # TODO send back the massege with task
        elif type == MessageTaskToCompute.Type:
            pass # TODO intepret and start computing
        else:
            assert False