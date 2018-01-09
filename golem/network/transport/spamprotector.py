import time
import logging
from golem_messages.message import Message
from golem_messages.message import P2P_MESSAGE_BASE

logger = logging.getLogger(__name__)


class SpamProtector:

    SetTaskSessionFrq = 20
    SetTaskSessionType = P2P_MESSAGE_BASE + 16

    FeqDict = { SetTaskSessionType: SetTaskSessionFrq}

    def __init__(self):

        self.last_msg_map = dict()

    def check_msg(self, msg):
        if msg is None:
            return False

        msg_type, timestamp, is_encoded = Message.deserialize_header(
            msg[:Message.HDR_LEN])
        return self._check_msg_type(msg_type)

    def _check_msg_type(self, msg_type):
        if msg_type == __class__.SetTaskSessionType:
            return not self.is_spamming(msg_type)
        else:
            return True

    def is_spamming(self, msg_type):
        if msg_type in self.last_msg_map:
            if self.last_msg_map[msg_type] - int(time.time()) < __class__.FeqDict[msg_type]:
                logger.debug("DROPING SPAM message")
                return True

        self.last_msg_map[msg_type] = int(time.time())
        return False


