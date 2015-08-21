import logging
import time

#from golem.network.p2p.NetConnState import NetConnState
from golem.network.transport.tcp_network import SafeProtocol
from golem.core.variables import LONG_STANDARD_SIZE

logger = logging.getLogger(__name__)


class NetAndFilesConnState(SafeProtocol):
    ############################
    def __init__(self, server = None):
        SafeProtocol.__init__(self, server)

        self.fileMode = False
        self.fileConsumer = None

        self.dataMode = False
        self.dataConsumer = None

        self.fileProducer = None

    ############################
    def _interpret(self, data):

        self.session.lastMessageTime = time.time()

        if self.fileMode:
            self.fileDataReceived(data)
            return

        if self.dataMode:
            self.resultDataReceived(data)
            return

        SafeProtocol._interpret(self, data)

    ############################
    def fileDataReceived(self, data ):
        assert self.fileConsumer
        assert len(data) >= LONG_STANDARD_SIZE

        self.fileConsumer.dataReceived(data)

    ############################
    def resultDataReceived(self, data):
        assert self.dataConsumer
        assert len(data) >= LONG_STANDARD_SIZE

        self.dataConsumer.dataReceived(data)

    ############################
    def clean(self):
        if self.dataConsumer is not None:
            self.dataConsumer.close()

        if self.fileConsumer is not None:
            self.fileConsumer.close()

        if self.fileProducer is not None:
            self.fileProducer.close()

####################################################################################
class MidNetAndFilesConnState(NetAndFilesConnState):
    ############################
    def _interpret(self, data):
        if self.session.isMiddleman:
            self.session.lastMessageTime = time.time()
            self.db.appendString(data)
            self.session.interpret(self.db.readAll())
        else:
            NetAndFilesConnState._interpret(self, data)

    ############################
    def _prepare_msg_to_send(self, msg):
        if self.session.isMiddleman:
            return msg
        else:
            return NetAndFilesConnState._prepare_msg_to_send(self, msg)







