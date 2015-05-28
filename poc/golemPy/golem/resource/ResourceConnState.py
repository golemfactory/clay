import logging
import time


from golem.network.p2p.NetConnState import NetConnState

logger = logging.getLogger(__name__)

class ResourceConnState( NetConnState ):
    ############################
    def __init__( self, server = None):
        NetConnState.__init__( self, server )
        self.fileMode = False

    ############################
    def _interpret(self, data):

        self.session.lastMessageTime = time.time()

        if self.fileMode:
            self.fileDataReceived( data )
            return

        NetConnState._interpret(self, data)

    ############################
    def fileDataReceived( self, data  ):
        self.session.fileDataReceived( data )
