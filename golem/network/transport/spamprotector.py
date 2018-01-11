import time
import logging
from golem_messages.message import Message, SetTaskSession

logger = logging.getLogger(__name__)


class SpamProtector:

    SetTaskSessionInterval = 20

    INTERVALS = {SetTaskSession.TYPE: SetTaskSessionInterval}

    def __init__(self):

        self.last_msg_map = dict()

    def check_msg(self, msg):
        if msg is None:
            return False

        msg_type, _, _ = Message.deserialize_header(msg[:Message.HDR_LEN])

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
