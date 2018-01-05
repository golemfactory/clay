import abc
import golem_messages
from golem_messages import message
import logging
import semantic_version
import time

from golem import utils
from golem.core.keysauth import get_random_float
from golem.core.variables import UNVERIFIED_CNT
from .network import Session

logger = logging.getLogger(__name__)


def is_golem_messages_version_compatible(theirs_gm_version):
    try:
        theirs_v = semantic_version.Version(theirs_gm_version)
    except ValueError:
        logger.debug("Version parsing error.", exc_info=True)
        return False
    ours_v = semantic_version.Version(golem_messages.__version__)
    spec_str = '>={major}.{minor}.0,<{next_minor}'.format(
        major=ours_v.major,
        minor=ours_v.minor,
        next_minor=ours_v.next_minor(),
    )
    spec = semantic_version.Spec(spec_str)
    if theirs_v not in spec:
        return False
    return True


class FileSession(Session, metaclass=abc.ABCMeta):
    """ Abstract class that represents session interface with additional operations for
    receiving files """

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
        self._interpretation = {
            message.Disconnect.TYPE: self._react_to_disconnect,
            message.Hello.TYPE: self._react_to_hello,
        }
        # Message interpretation - dictionary where keys are messages' types and values are functions that should
        # be called after receiving specific message
        self.conn.server.pending_sessions.add(self)

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
            self.disconnect(message.Disconnect.REASON.BadProtocol)

    def dropped(self):
        """ Close connection """
        self.conn.close()
        try:
            self.conn.server.pending_sessions.remove(self)
        except KeyError:
            pass

    def close_now(self):
        """ Close connection quickly without flushing buffors or waiting for producents. """
        self.conn.close_now()
        try:
            self.conn.server.pending_sessions.remove(self)
        except KeyError:
            pass

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
            self.send(message.Disconnect(reason=reason))

    def _check_msg(self, msg):
        if msg is None or not isinstance(msg, message.Message):
            self.disconnect(message.Disconnect.REASON.BadProtocol)
            return False
        return True

    def _react_to_hello(self, msg):
        theirs_gm_version = msg.golem_messages_version
        if not is_golem_messages_version_compatible(theirs_gm_version):
            logger.info(
                'Incompatible golem_messages: %s (ours) != %s (theirs)',
                golem_messages.__version__,
                theirs_gm_version,
            )
            self.disconnect(message.Disconnect.REASON.BadProtocol)
            return

    def _react_to_disconnect(self, msg):
        logger.info("Disconnect reason: {}".format(msg.reason))
        logger.info("Closing {} : {}".format(self.address, self.port))
        self.dropped()


class BasicSafeSession(BasicSession):
    """Enhance BasicSession with cryptographic operations logic (eg. accepting
    only encrypted or signed messages) and connection verifications logic.
    Cryptographic operation should be implemented in descendant class.
    """

    def __init__(self, conn):
        super().__init__(conn)
        self.key_id = 0
        self.unverified_cnt = UNVERIFIED_CNT  # how many unverified messages can be stored before dropping connection
        self.rand_val = get_random_float()  # TODO: change rand val to hashcash
        self.verified = False
        # React to message even if it's self.verified is set to False
        self.can_be_unverified = [message.Disconnect.TYPE]
        # React to message even if it's not encrypted.
        self.can_be_not_encrypted = [message.Disconnect.TYPE]

    @property
    def theirs_public_key(self):
        if not self.key_id:
            return None
        return utils.decode_hex(self.key_id)

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
                self.disconnect(message.Disconnect.REASON.Unverified)
            return

        BasicSession.send(self, message)

    def _can_send(self, msg, send_unverified):
        return self.verified or send_unverified or msg.TYPE in self.can_be_unverified

    def _check_msg(self, msg):
        if not BasicSession._check_msg(self, msg):
            return False

        type_ = msg.TYPE

        if not self.verified and type_ not in self.can_be_unverified:
            self.disconnect(message.Disconnect.REASON.Unverified)
            return False

        if not msg.encrypted and type_ not in self.can_be_not_encrypted:
            self.disconnect(message.Disconnect.REASON.BadProtocol)
            return False

        return True

