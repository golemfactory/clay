import abc
import logging
import random
import time

from golem.core.keysauth import get_random_float
from golem.core.variables import MSG_TTL, FUTURE_TIME_TOLERANCE, UNVERIFIED_CNT
from golem.network.transport import message
from network import Session

logger = logging.getLogger(__name__)


class SafeSession(Session):
    """ Abstract class that represents session interface with additional opperations for cryptographic
    operations (signing, veryfing, encrypting and decrypting data). """
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def sign(self, msg):
        return

    @abc.abstractmethod
    def verify(self, msg):
        return

    @abc.abstractmethod
    def encrypt(self, data):
        return

    @abc.abstractmethod
    def decrypt(self, data):
        return


class FileSession(Session):
    """ Abstract class that represents session interface with additional operations for
    receiving files """
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def data_sent(self, extra_data=None):
        return

    @abc.abstractmethod
    def full_data_received(self, extra_data=None):
        return

    @abc.abstractmethod
    def production_failed(self, extra_data=None):
        return


class BasicSession(FileSession):
    """ Basic session responsible for managing the connection and reacting to different types
    of messages.
    """

    # Disconnect reasons
    DCRProtocolVersion = "Protocol version"
    DCRBadProtocol = "Bad protocol"
    DCRTimeout = "Timeout"
    DCRNoMoreMessages = "No more messages"

    def __init__(self, conn):
        """
        Create new Session
        :param Protocol conn: connection protocol implementation that this session should enhance.
        """
        Session.__init__(self, conn)
        self.conn = conn

        pp = conn.transport.getPeer()
        self.address = pp.host
        self.port = pp.port

        self.last_message_time = time.time()
        self._disconnect_sent = False
        self._interpretation = {message.MessageDisconnect.TYPE: self._react_to_disconnect}
        # Message interpretation - dictionary where keys are messages' types and values are functions that should
        # be called after receiving specific message

    def interpret(self, msg):
        """
        React to specific message. Disconnect, if message type is unknown for that session.
        :param Message msg: Message to interpret and react to.
        :return None:
        """
        self.last_message_time = time.time()

        if not self._check_msg(msg):
            return

        action = self._interpretation.get(msg.TYPE)
        if action:
            action(msg)
        else:
            self.disconnect(BasicSession.DCRBadProtocol)

    def dropped(self):
        """ Close connection """
        self.conn.close()

    def close_now(self):
        """ Close connection quickly without flushing buffors or waiting for producents. """
        self.conn.close_now()

    def disconnect(self, reason):
        """ Send "disconnect" message to the peer and drop the connection.
        :param string reason: Reason for disconnecting. Should use global class disconnect reasons, eg. DCRBadProtocol
        """
        logger.info("Disconnecting {} : {} reason: {}".format(self.address, self.port, reason))
        if self.conn.opened:
            self._send_disconnect(reason)
            self.dropped()

    def send(self, message):
        """ Send given message.
        :param Message message: message to be sent.
        """
        # print "Sending to {}:{}: {}".format(self.address, self.port, message)

        if not self.conn.send_message(message):
            self.dropped()
            return

    def data_sent(self, extra_data=None):
        """ All data that should be send in stream mode has been send.
        :param dict|None extra_data: additional information that may be needed
        """
        if self.conn.producer:
            self.conn.producer.close()
            self.conn.producer = None

    def production_failed(self, extra_data=None):
        """ Producer encounter error and stopped sending data in stream mode
        :param dict|None extra_data: additional information that may be needed
        """
        self.dropped()

    def full_data_received(self, extra_data=None):
        pass

    def _send_disconnect(self, reason):
        """ :param string reason: reason to disconnect """
        if not self._disconnect_sent:
            self._disconnect_sent = True
            self.send(message.MessageDisconnect(reason=reason))

    def _check_msg(self, msg):
        if msg is None or not isinstance(msg, message.Message):
            self.disconnect(BasicSession.DCRBadProtocol)
            return False
        return True

    def _react_to_disconnect(self, msg):
        logger.info("Disconnect reason: {}".format(msg.reason))
        logger.info("Closing {} : {}".format(self.address, self.port))
        self.dropped()


class BasicSafeSession(BasicSession, SafeSession):
    """ Enhance BasicSession with cryptographic operations logic (eg. accepting only encrypted or signed messages)
    and connection verifications logic.
    Cryptographic operation should be implemented in descendant class.
    """

    # Disconnect reasons
    DCROldMessage = "Message expired"
    DCRWrongTimestamp = "Wrong timestamp"
    DCRUnverified = "Unverified connection"
    DCRWrongEncryption = "Wrong encryption"

    def __init__(self, conn):
        BasicSession.__init__(self, conn)
        self.key_id = 0
        self.message_ttl = MSG_TTL  # how old messages should be accepted
        self.future_time_tolerance = FUTURE_TIME_TOLERANCE  # how much greater time than current time should be accepted
        self.unverified_cnt = UNVERIFIED_CNT  # how many unverified messages can be stored before dropping connection
        self.rand_val = get_random_float()  # TODO: change rand val to hashcash
        self.verified = False
        self.can_be_unverified = [message.MessageDisconnect.TYPE]  # React to message even if it's self.verified is set to False
        self.can_be_unsigned = [message.MessageDisconnect.TYPE]  # React to message even if it's not signed.
        self.can_be_not_encrypted = [message.MessageDisconnect.TYPE]  # React to message even if it's not encrypted.

    # Simple session with no encryption and no signing
    def sign(self, msg):
        return msg

    def verify(self, msg):
        return True

    def encrypt(self, data):
        return data

    def decrypt(self, data):
        return data

    def send(self, message, send_unverified=False):
        """ Send given message if connection was verified or send_unverified option is set to True.
        :param Message message: message to be sent.
        :param boolean send_unverified: should message be sent even if the connection hasn't been verified yet?
        """
        if not self._can_send(message, send_unverified):
            logger.info("Connection hasn't been verified yet, not sending message {} to {} {}"
                        .format(message, self.address, self.port))
            self.unverified_cnt -= 1
            if self.unverified_cnt <= 0:
                self.disconnect(BasicSafeSession.DCRUnverified)
            return

        BasicSession.send(self, message)

    def _can_send(self, msg, send_unverified):
        return self.verified or send_unverified or msg.TYPE in self.can_be_unverified

    def _check_msg(self, msg):
        if not BasicSession._check_msg(self, msg):
            return False

        if not self._verify_time(msg):
            return False

        type_ = msg.TYPE

        if not self.verified and type_ not in self.can_be_unverified:
            self.disconnect(BasicSafeSession.DCRUnverified)
            return False

        if not msg.encrypted and type_ not in self.can_be_not_encrypted:
            self.disconnect(BasicSafeSession.DCRBadProtocol)
            return False

        if (type_ not in self.can_be_unsigned) and (not self.verify(msg)):
            logger.error("Failed to verify message signature ({} from {}:{})"
                         .format(msg, self.address, self.port))
            self.disconnect(BasicSafeSession.DCRUnverified)
            return False

        return True

    def _verify_time(self, msg):
        """ Verify message timestamp. If message is to old or have timestamp from distant future return False.
        """
        try:
            if self.last_message_time - msg.timestamp > self.message_ttl:
                self.disconnect(BasicSafeSession.DCROldMessage)
                return False
            elif msg.timestamp - self.last_message_time > self.future_time_tolerance:
                self.disconnect(BasicSafeSession.DCRWrongTimestamp)
                return False
        except TypeError:
            return False

        return True


class MiddlemanSafeSession(BasicSafeSession):
    """ Enhance BasicSafeSession with logic that supports middleman connection. If is_middleman variable is set True,
        that cryptographic logic should not apply and data should be transfer to open_session without addtional
        interpretations.
    """
    def __init__(self, conn):
        BasicSafeSession.__init__(self, conn)

        self.is_middleman = False
        self.open_session = None  # transfer data to that session in middleman mode
        self.middleman_conn_data = None

    def send(self, message, send_unverified=False):
        """ Send given message if connection was verified or send_unverified option is set to True.
        :param Message message: message to be sent.
        :param boolean send_unverified: should message be sent even if the connection hasn't been verified yet?
        """
        if not self.is_middleman:
            BasicSafeSession.send(self, message, send_unverified)
        else:
            BasicSession.send(self, message)

    def interpret(self, msg):
        """ React to specific message. Disconnect, if message type is unknown for that session.
        In middleman mode doesn't react to message, just sends it to other open session.
        :param Message msg: Message to interpret and react to.
        :return None:
        """
        if not self.is_middleman:
            BasicSafeSession.interpret(self, msg)
        else:
            self.last_message_time = time.time()

            if self.open_session is None:
                logger.error("Destination session for middleman don't exist")
                self.dropped()
            self.open_session.send(msg)

    def dropped(self):
        """ If it's called for the first time, send "disconnect" message to the peer. Otherwise, drops
        connection.
        In middleman mode additionally drops the other open session.
        """
        if self.is_middleman and self.open_session:
            open_session = self.open_session
            self.open_session = None
            open_session.dropped()
        BasicSafeSession.dropped(self)

    def _check_msg(self, msg):
        if not self.is_middleman:
            return BasicSafeSession._check_msg(self, msg)
        else:
            return BasicSession._check_msg(self, msg)
