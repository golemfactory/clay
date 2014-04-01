import time
import sys

class ClientManagerSession:
    ##########################
    def __init__( self, conn, client ):
        self.conn       = conn
        self.client     = client

    ##########################
    def dropped( self ):
        self.conn.close()

    ##########################
    def interpret( self, msg ):

        type = msg.getType()

        if type == MessageNewTask.Type:
            task = pickle.loads( msg.data )
            task.header.taskOwnerAddress = self.server.taskServer.address
            task.header.taskOwnerPort = self.server.taskServer.curPort
            self.server.taskServer.taskManager.addNewTask( task )

        elif type == MessageKillNode.Type:
            self.dropped()
            time.sleep( 0.5 )

            os.system( "taskkill /PID {} /F".format( os.getpid() ) )
        else:
            print "Wrong message received {}".format( msg )

    ##########################
    def sendClientStateSnapshot( self, snapshot ):
        if self.conn and self.conn.isOpen():
            self.conn.sendMessage( MessagePeerStatus( snapshot.uid, pickle.dumps( snapshot ) ) )