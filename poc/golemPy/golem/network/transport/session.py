import abc
import random
import time
import logging

from golem.Message import MessageDisconnect

logger = logging.getLogger(__name__)


from network import Session


class SafeSession(Session):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def sign(self, msg):
        return

    @abc.abstractmethod
    def verify(self, msg):
        return

    @abc.abstractmethod
    def encrypt(self, msg):
        return

    @abc.abstractmethod
    def decrypt(self, msg):
        return


class BasicSession(Session):

    DCRBadProtocol = "Bad protocol"
    DCRTimeout = "Timeout"

    def __init__(self, conn):
        Session.__init__(self, conn)
        self.conn = conn

        pp = conn.transport.getPeer()
        self.address = pp.host
        self.port = pp.port

        self.last_message_time = time.time()
        self.lastDisconnectTime = None
        self.interpretation = {MessageDisconnect.Type: self._react_to_disconnect}

        self.extraData = {}

    def interpret(self, msg):
        self.last_message_time = time.time()

        # print "Receiving from {}:{}: {}".format(self.address, self.port, msg)

        if not self._check_msg(msg):
            return

        action = self.interpretation.get(msg.getType())
        if action:
            action(msg)
        else:
            self.disconnect(BasicSession.DCRBadProtocol)

    def dropped(self):
        self.conn.close()

    def close_now(self):
        self.conn.close_now()

    def disconnect(self, reason):
        logger.info("Disconnecting {} : {} reason: {}".format(self.address, self.port, reason))
        if self.conn.opened:
            if self.lastDisconnectTime:
                self.dropped()
            else:
                self.lastDisconnectTime = time.time()
                self._send_disconnect(reason)

    def _send_disconnect(self, reason):
        self.send(MessageDisconnect(reason))

    def send(self, message):
        #  "Sending to {}:{}: {}".format(self.address, self.port, message)

        if not self.conn.send_message(message):
            self.dropped()
            return

    def _check_msg(self, msg):
        if msg is None:
            self.disconnect(BasicSession.DCRBadProtocol)
            return False
        return True

    def _react_to_disconnect(self, msg):
        logger.info("Disconnect reason: {}".format(msg.reason))
        logger.info("Closing {} : {}".format(self.address, self.port))
        self.dropped()


class BasicSafeSession(BasicSession, SafeSession):

    DCROldMessage = "Message expired"
    DCRWrongTimestamp = "Wrong timestamp"
    DCRUnverified = "Unverifed connection"
    DCRWrongEncryption = "Wrong encryption"

    def __init__(self, conn):
        BasicSession.__init__(self, conn)
        self.clientKeyId = 0
        self.messageTTL = 600
        self.futureTimeTolerance = 300
        self.unverifiedCnt = 15
        self.randVal = random.random()
        self.verified = False
        self.canBeUnverified = [MessageDisconnect]
        self.canBeUnsigned = [MessageDisconnect]
        self.canBeNotEncrypted = [MessageDisconnect]

    # Simple session with no encryption and no signing
    def sign(self, msg):
        return msg

    def verify(self, msg):
        return True

    def encrypt(self, msg):
        return msg

    def decrypt(self, msg):
        return msg

    def send(self, message, send_unverified=False):
        if not self.verified and not send_unverified:
            logger.info("Connection hasn't been verified yet, not sending message")
            self.unverifiedCnt -= 1
            if self.unverifiedCnt <= 0:
                self.disconnect(BasicSafeSession.DCRUnverified)
            return

        BasicSession.send(self, message)

    def _check_msg(self, msg):
        if not BasicSession._check_msg(self, msg):
            return False

        if not self._verify_time(msg):
            return False

        type_ = msg.getType()

        if not self.verified and type_ not in self.canBeUnverified:
            self.disconnect(BasicSafeSession.DCRUnverified)
            return False

        if not msg.encrypted and type_ not in self.canBeNotEncrypted:
            self.disconnect(BasicSafeSession.DCRBadProtocol)
            return False

        if (type_ not in self.canBeUnsigned) and (not self.verify(msg)):
            logger.error("Failed to verify message signature")
            self.disconnect(BasicSafeSession.DCRUnverified)
            return False

        return True

    def _verify_time(self, msg):
        if self.last_message_time - msg.timestamp > self.messageTTL:
            self.disconnect(BasicSafeSession.DCROldMessage)
            return False
        elif msg.timestamp - self.last_message_time > self.futureTimeTolerance:
            self.disconnect(BasicSafeSession.DCRWrongTimestamp)
            return False

        return True


class MiddlemanSafeSession(BasicSafeSession):
    def __init__(self, conn):
        BasicSafeSession.__init__(self, conn)

        self.is_middleman = False
        self.open_session = None
        self.askingNodeKeyId = None
        self.middlemanConnData = None

    def send(self, message, send_unverified=False):
        if not self.is_middleman:
            BasicSafeSession.send(self, message, send_unverified)
        else:
            BasicSession.send(self, message)

    def _check_msg(self, msg):
        if not self.is_middleman:
            return BasicSafeSession._check_msg(self, msg)
        else:
            return BasicSession._check_msg(self, msg)

    def interpret(self, msg):
        if not self.is_middleman:
            BasicSafeSession.interpret(self, msg)
        else:
            self.last_message_time = time.time()

            if self.open_session is None:
                logger.error("Destination session for middleman don't exist")
                self.dropped()
            self.open_session.send(msg)

    def dropped(self):
        if not self.is_middleman:
            BasicSafeSession.dropped(self)
        else:
            if self.open_session:
                open_session = self.open_session
                self.open_session = None
                open_session.dropped()
            BasicSafeSession.dropped(self)
