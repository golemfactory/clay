import logging
import time

from golem.network.p2p.NetConnState import NetConnState
from golem.core.variables import LONG_STANDARD_SIZE

logger = logging.getLogger(__name__)

class ResourceConnState( NetConnState ):
    ############################
    def __init__( self, server = None):
        NetConnState.__init__( self, server )
        self.fileMode = False

        self.fileConsumer = None
        self.fileProducer = None

    ############################
    def _interpret(self, data):

        self.session.lastMessageTime = time.time()

        if self.fileMode:
            self.fileDataReceived( data )
            return

        NetConnState._interpret(self, data)

    ############################
    def fileDataReceived( self, data  ):
        assert self.fileConsumer
        assert len( data ) >= LONG_STANDARD_SIZE

        self.fileConsumer.dataReceived( data )

    ############################
    def clean(self):
        if self.fileConsumer is not None:
            self.fileConsumer.close()

        if self.fileProducer is not None:
            self.fileProducer.close()