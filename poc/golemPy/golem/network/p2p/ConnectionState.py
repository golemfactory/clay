import abc
import logging

from twisted.internet.protocol import Protocol
from golem.Message import Message
from golem.core.databuffer import DataBuffer

logger = logging.getLogger(__name__)

class ConnectionState(Protocol):
    ############################
    def __init__(self):
        self.opened = False
        self.db = DataBuffer()
        self.session = None

    ############################
    def setSession(self, session):
        self.session = session

    ############################
    def sendMessage(self, msg):
        if not self.opened:
            logger.error(msg)
            logger.error("sendMessage failed - connection closed.")
            return False

        msgToSend = self._prepareMsgToSend(msg)

        if msgToSend is None:
            return False

        self.transport.getHandle()
        self.transport.write(msgToSend)

        return True

    ############################
    def close(self):
        self.transport.loseConnection()

    ############################
    def isOpen(self):
        return self.opened

    ############################
    def connectionMade(self):
        """Called when new connection is successfully opened"""
        self.opened = True

    ############################
    def dataReceived(self, data):
        """Called when additional chunk of data is received from another peer"""
        if not self._canReceive():
            return None

        if not self.session:
            logger.warning( "No session argument in connection state" )
            return None

        self._interpret(data)


    ############################
    def connectionLost(self, reason):
        """Called when connection is lost (for whatever reason)"""
        self.opened = False
        if self.session:
            self.session.dropped()

    ############################
    def _prepareMsgToSend(self, msg):
        serMsg = msg.serialize()

        db = DataBuffer()
        db.appendLenPrefixedString(serMsg)
        return db.readAll()

    ############################
    def _canReceive(self):
        assert self.opened
        assert isinstance(self.db, DataBuffer)
        return True

    ############################
    def _interpret(self, data):
        self.db.appendString(data)
        mess = self._dataToMessages()
        if mess is None or len(mess) == 0:
            logger.error( "Deserialization message failed" )
            return None

        for m in mess:
            self.session.interpret(m)

    ############################
    def _dataToMessages(self):
        return Message.deserialize(self.db)