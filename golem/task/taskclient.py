import logging
from threading import Lock

logger = logging.getLogger(__name__)


class TaskClient(object):
    def __init__(self, node_id):
        self.node_id = node_id
        self._accepted = 0
        self._rejected = 0
        self._started = 0
        self._finishing = 0
        self._lock = Lock()

    def __setstate__(self, state):
        self.__dict__ = state
        self._lock = Lock()

    def __getstate__(self):
        state = self.__dict__.copy()
        del state['_lock']
        return state

    @staticmethod
    def assert_exists(node_id, node_dict):
        if node_id not in node_dict:
            node_dict[node_id] = TaskClient(node_id)
        return node_dict[node_id]

    def accept(self):
        with self._lock:
            self._accepted += 1
            self._completed()

    def reject(self):
        with self._lock:
            self._rejected += 1
            self._completed()

    def start(self):
        with self._lock:
            self._started += 1

    def finish(self):
        with self._lock:
            self._finishing += 1

    def accepted(self):
        with self._lock:
            return self._accepted

    def rejected(self):
        with self._lock:
            return self._rejected

    def started(self):
        with self._lock:
            return self._started

    def finishing(self):
        with self._lock:
            return self._finishing

    def _completed(self):
        self._started -= 1
        self._finishing -= 1
