from message import MessagePeerStatus, MessageNewTask, MessageKillNode
import os
import pickle
import time
import sys

class ServerManagerSession:

    ##########################
    def __init__( self, conn, address, port, server ):
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