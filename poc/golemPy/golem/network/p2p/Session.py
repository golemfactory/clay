import random
import time
import logging

from golem.Message import MessageDisconnect

logger = logging.getLogger(__name__)


##############################################################################

class SessionInterface:
    ##########################
    def __init__(self, conn):
        pass

    ##########################
    def dropped(self):
        pass

    ##########################
    def interpret(self, msg):
        pass

    ##########################
    def disconnect(self, reason):
        pass

##############################################################################

class NetSessionInterface(SessionInterface):
    ##########################
    def sign(self, msg):
        pass

    ##########################
    def verify(self, msg):
        pass

    ##########################
    def encrypt(self, msg):
        pass

    ##########################
    def decrypt(self, msg):
        pass

##############################################################################

class Session(SessionInterface):

    DCRBadProtocol      = "Bad protocol"
    DCRTimeout          = "Timeout"

    ##########################
    def __init__(self, conn):
        self.conn = conn

        pp = conn.transport.getPeer()
        self.address = pp.host
        self.port = pp.port

        self.last_message_time = time.time()
        self.last_disconnect_time = None
        self._interpretation = { MessageDisconnect.Type: self._reactToDisconnect }

        self.extraData = {}

    ##########################
    def interpret(self, msg):
        self.last_message_time = time.time()

        # print "Receiving from {}:{}: {}".format(self.address, self.port, msg)

        if not self._checkMsg(msg):
            return

        action = self._interpretation.get(msg.getType())
        if action:
            action(msg)
        else:
            self.disconnect(Session.DCRBadProtocol)

    ##########################
    def dropped(self):
        self.conn.close()

    ##########################
    def closeNow(self):
        self.conn.closeNow()

    ##########################
    def disconnect(self, reason):
        logger.info("Disconnecting {} : {} reason: {}".format(self.address, self.port, reason))
        if self.conn.isOpen():
            if self.last_disconnect_time:
                self.dropped()
            else:
                self.last_disconnect_time = time.time()
                self._sendDisconnect(reason)

    ##########################
    def _sendDisconnect(self, reason):
        self.send(MessageDisconnect(reason))

    ##########################
    def send(self, message):
        # print "Sending to {}:{}: {}".format(self.address, self.port, message)

        if not self.conn.send_message(message):
            self.dropped()
            return

    ##########################
    def _checkMsg(self, msg):
        if msg is None:
            self.disconnect(Session.DCRBadProtocol)
            return False
        return True

    ##########################
    def _reactToDisconnect(self, msg):
        logger.info("Disconnect reason: {}".format(msg.reason))
        logger.info("Closing {} : {}".format(self.address, self.port))
        self.dropped()


##############################################################################

class NetSession(Session, NetSessionInterface):

    DCROldMessage       = "Message expired"
    DCRWrongTimestamp   = "Wrong timestamp"
    DCRUnverified       = "Unverifed connection"
    DCRWrongEncryption  = "Wrong encryption"

    ##########################
    def __init__(self, conn):
        Session.__init__(self, conn)
        self.clientKeyId = 0
        self.messageTTL = 600
        self.futureTimeTolerance = 300
        self.unverifiedCnt = 15
        self.randVal = random.random()
        self.verified = False
        self.can_be_unverified = [MessageDisconnect]
        self.can_be_unsigned = [MessageDisconnect]
        self.can_be_not_encrypted = [MessageDisconnect]

    #Simple session with no encryption and no signing
    ##########################
    def sign(self, msg):
        return msg

    ##########################
    def verify(self, msg):
        return True

    ##########################
    def encrypt(self, msg):
        return msg

    ##########################
    def decrypt(self, msg):
        return msg

    #########################
    def send(self, message, sendUnverified = False):
        if not self.verified and not sendUnverified :
            logger.info("Connection hasn't been verified yet, not sending message")
            self.unverifiedCnt -= 1
            if self.unverifiedCnt <= 0:
                self.disconnect(NetSession.DCRUnverified)
            return

        Session.send(self, message)

    ##########################
    def _checkMsg(self, msg):
        if not Session._checkMsg(self, msg):
            return False

        if not self._verifyTime(msg):
            return False

        type = msg.getType()

        if not self.verified and type not in self.can_be_unverified:
            self.disconnect(NetSession.DCRUnverified)
            return False

        if not msg.encrypted and type not in self.can_be_not_encrypted:
            self.disconnect(NetSession.DCRBadProtocol)
            return False

        if (not type in self.can_be_unsigned) and (not self.verify(msg)):
            logger.error("Failed to verify message signature")
            self.disconnect(NetSession.DCRUnverified)
            return False

        return True

    ##########################
    def _verifyTime(self, msg):
        if self.last_message_time - msg.timestamp > self.messageTTL:
            self.disconnect(NetSession.DCROldMessage)
            return False
        elif msg.timestamp - self.last_message_time > self.futureTimeTolerance:
            self.disconnect(NetSession.DCRWrongTimestamp)
            return False

        return True

##############################################################################
class MidNetSession(NetSession):
    ##########################
    def __init__(self, conn):
        NetSession.__init__(self, conn)

        self.is_middleman = False
        self.openSession = None
        self.askingNodeKeyId = None
        self.middlemanConnData = None

    ##########################
    def send(self, message, sendUnverified=False):
        if not self.is_middleman:
            NetSession.send(self, message, sendUnverified)
        else:
            Session.send(self, message)

    ##########################
    def _checkMsg(self, msg):
        if not self.is_middleman:
            return NetSession._checkMsg(self, msg)
        else:
            return Session._checkMsg(self, msg)

    ##########################
    def interpret(self, msg):
        if not self.is_middleman:
            NetSession.interpret(self, msg)
        else:
            self.last_message_time = time.time()

            if self.openSession is None:
                logger.error("Destination session for middleman don't exist")
                self.dropped()
            self.openSession.send(msg)

    ##########################
    def dropped(self):
        if not self.is_middleman:
            NetSession.dropped(self)
        else:
            if self.openSession:
                openSession = self.openSession
                self.openSession = None
                openSession.dropped()
            NetSession.dropped(self)