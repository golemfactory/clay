from message import MessagePeerStatus, MessageNewTask, MessageKillNode
import os
import pickle
import time
import sys

class ManagerSession:

    ##########################
    def __init__( self, conn, server, address, port ):
        self.conn       = conn
        self.server     = server
        self.address    = address
        self.port       = port
        self.uid        = None

    ##########################
    def dropped( self ):
        self.conn.close()
        self.server.managerSession = None
        self.server.managerSessionDisconnected( self.uid )

    ##########################
    def interpret( self, msg ):

        type = msg.getType()

        if type == MessagePeerStatus.Type:
            nss = pickle.loads( msg.data )
            self.uid = nss.getUID()
            self.server.nodeStateSnapshotReceived( nss )

        elif type == MessageNewTask.Type:
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

    def sendKillNode( self ):
        if self.conn and self.conn.isOpen():
            self.conn.sendMessage( MessageKillNode() )


    ##########################
    def sendNewTask( self, task ):
        if self.conn and self.conn.isOpen():
            tp = pickle.dumps( task )
            self.conn.sendMessage( MessageNewTask( tp ) )