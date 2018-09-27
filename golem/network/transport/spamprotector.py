import time
import logging
from golem_messages.register import library
from golem_messages import message
from golem_messages.message.base import Message

logger = logging.getLogger(__name__)


class SpamProtector:

    SetTaskSessionInterval = 20

    INTERVALS = {
        library.get_type(message.p2p.SetTaskSession): SetTaskSessionInterval,
    }

    def __init__(self):

        self.last_msg_map = dict()

    def check_msg(self, msg_data):
        if msg_data is None:
            return False

        msg_type, _, _ = Message.unpack_header(msg_data[:Message.HDR_LEN])

        if msg_type not in self.INTERVALS:
            return True

        now = int(time.time())
        last_received = self.last_msg_map.get(msg_type, 0)
        delta = now - last_received
        if delta > self.INTERVALS[msg_type]:
            self.last_msg_map[msg_type] = now
            return True

        logger.debug("DROPPING SPAM message")
        return False
