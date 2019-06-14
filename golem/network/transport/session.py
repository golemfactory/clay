import abc
import logging
import time
from enum import Enum
from typing import Optional

from golem_messages import message

from golem import utils
from golem.core.keysauth import get_random_float
from golem.core.variables import UNVERIFIED_CNT
from .network import Session

logger = logging.getLogger(__name__)


class ConnTypes:
    p2p = 0
    task = 1


class BasicSession(Session):
    """Basic session responsible for managing the connection and reacting
       to different types of messages.
    """

    ProtocolId = b"\0\0\0"

    def __init__(self, conn):
        """
        Create new Session
        :param Protocol conn: connection protocol implementation that
                              this session should enhance.
        """
        Session.__init__(self, conn)

        pp = conn.transport.getPeer()
        self.address = pp.host
        self.port = pp.port

        self.last_message_time = time.time()
        self._disconnect_sent = False
        self._interpretation = {
            message.base.Disconnect: self._react_to_disconnect,
        }
        # Message interpretation - dictionary where keys are message types
        # and values are functions that should
        # be called after receiving specific message
        self.conn.server.pending_sessions.add(self)

    def __str__(self):
        if self._disconnect_sent:
            disconnect_s = ' #disconnect_sent'
        else:
            disconnect_s = ''
        lmt = time.time() - self.last_message_time
        return (
            f"{ self.__class__.__name__ } with { self.address }:{ self.port }"
            f" (LMT: { lmt }s){ disconnect_s }"
        )

    def __repr__(self):
        return f"<{ str(self) }>"

    def interpret(self, msg: message.base.Message):
        """
        React to specific message. Disconnect, if message type is unknown
        for that session.
        :param Message msg: Message to interpret and react to.
        :return None:
        """
        self.last_message_time = time.time()

        if not self._check_msg(msg):
            return

        action = self._interpretation.get(msg.__class__)
        if action:
            action(msg)
        else:
            self.disconnect(message.base.Disconnect.REASON.BadProtocol)

    def dropped(self):
        """ Close connection """
        self.conn.close()
        try:
            self.conn.server.pending_sessions.remove(self)
        except KeyError:
            pass

    def disconnect(self, reason: message.base.Disconnect.REASON):
        """ Send "disconnect" message to the peer and drop the connection.
        :param string reason: Reason for disconnecting.
        """
        logger.info("Sending disconnect message. reason=%s, address=%s:%r",
                    reason.name, self.address, self.port,)
        if self.conn.opened:
            self._send_disconnect(reason)
            self.dropped()

    def send(self, msg):
        """ Send given message.
        :param Message message: message to be sent.
        """
        if not self.conn.send_message(msg):
            self.dropped()
            return

    def _send_disconnect(self, reason: message.base.Disconnect.REASON):
        """ :param string reason: reason to disconnect """
        if not self._disconnect_sent:
            self._disconnect_sent = True
            self.send(message.base.Disconnect(reason=reason))

    def _check_msg(self, msg):
        if msg is None or not isinstance(msg, message.base.Message):
            self.disconnect(message.base.Disconnect.REASON.BadProtocol)
            return False
        return True

    def _react_to_disconnect(self, msg):
        logger.info("Received disconnect message. reason=%s, address=%s:%r",
                    msg.reason.name, self.address, self.port)
        self.dropped()


class BasicSafeSession(BasicSession):
    """Enhance BasicSession with cryptographic operations logic (eg. accepting
    only encrypted or signed messages) and connection verifications logic.
    Cryptographic operation should be implemented in descendant class.
    """

    def __init__(self, conn):
        super().__init__(conn)
        self.key_id: Optional[str] = None
        # how many unverified messages can be stored before dropping connection
        self.unverified_cnt = UNVERIFIED_CNT
        self.rand_val = get_random_float()
        self.verified = False
        # React to message even if it's self.verified is set to False
        self.can_be_unverified = [message.base.Disconnect]

    @property
    def theirs_public_key(self):
        if not self.key_id:
            return None
        return utils.decode_hex(self.key_id)

    def send(self, msg, send_unverified=False):  # noqa pylint: disable=arguments-differ
        """Send given message if connection was verified or send_unverified
           option is set to True.

        :param Message msg: message to be sent.
        :param boolean send_unverified: should message be sent even
                                        if the connection hasn't been
                                        verified yet?
        """
        if not self._can_send(msg, send_unverified):
            logger.info(
                "Connection hasn't been verified yet,"
                " not sending %r to %r:%r",
                msg,
                self.address,
                self.port,
            )
            self.unverified_cnt -= 1
            if self.unverified_cnt <= 0:
                self.disconnect(message.base.Disconnect.REASON.Unverified)
            return

        BasicSession.send(self, msg)

    def _can_send(self, msg: message.base.Message, send_unverified):
        return self.verified \
            or send_unverified \
            or msg.__class__ in self.can_be_unverified

    def _check_msg(self, msg):
        if not BasicSession._check_msg(self, msg):
            return False

        if not self.verified and msg.__class__ not in self.can_be_unverified:
            self.disconnect(message.base.Disconnect.REASON.Unverified)
            return False

        return True
