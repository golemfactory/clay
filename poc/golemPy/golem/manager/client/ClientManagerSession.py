
from golem.Message import MessagePeerStatus, MessageKillNode, MessageNewTask
from ClientManagerConnState import ClientManagerConnState

import cPickle as pickle
import time
import os
import logging

logger = logging.getLogger(__name__)

class ClientManagerSession:

    ConnectionStateType = ClientManagerConnState

    ##########################
    def __init__( self, conn ):
        self.conn       = conn
        self.client     = None

    ##########################
    def dropped( self ):
        self.conn.close()

    ##########################
    def interpret( self, msg ):

        assert self.client

        type = msg.getType()

        if type == MessageNewTask.Type:
            task = pickle.loads( msg.data )
            self.client.addNewTask( task )

        elif type == MessageKillNode.Type:
            self.dropped()
            time.sleep( 0.5 )

            os.system( "taskkill /PID {} /F".format( os.getpid() ) )
        else:
            logger.error( "Wrong message received {}".format( msg ) )

    ##########################
    def sendClientStateSnapshot( self, snapshot ):
        if self.conn and self.conn.isOpen():
            self.conn.sendMessage( MessagePeerStatus( snapshot.uid, pickle.dumps( snapshot ) ) )