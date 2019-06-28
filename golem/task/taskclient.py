import logging
from threading import Lock
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class TaskClient(object):
    def __init__(self):
        self._lock: Lock = Lock()
        self._started: int = 0
        self._accepted: int = 0
        self._rejected: int = 0
        self._wtct_hash: Optional[bytes] = None
        self._wtct_num_subtasks: int = 0

    def __setstate__(self, state):
        self.__dict__ = state
        self._lock = Lock()

    def __getstate__(self):
        state = self.__dict__.copy()
        del state['_lock']
        return state

    @staticmethod
    def get_or_initialize(node_id: str,
                          node_dict: Dict[str, 'TaskClient']) -> 'TaskClient':
        """ If given `node_id` is already in `node_dict` it's corresponding
        `TaskClient` instance is returned; otherwise an empty `TaskClient` is
        inserted into `node_dict` and returned
        """
        if node_id not in node_dict:
            node_dict[node_id] = TaskClient()
        return node_dict[node_id]

    def _reset(self):
        self._started = 0
        self._accepted = 0
        self._wtct_hash = None
        self._wtct_num_subtasks = 0

    def start(self, wtct_hash: bytes, num_subtasks: int) -> bool:
        if self.should_wait(wtct_hash) or self.rejected():
            return False

        with self._lock:
            self._wtct_hash = wtct_hash
            self._wtct_num_subtasks = num_subtasks
            self._started += 1

        return True

    def accept(self):
        with self._lock:
            self._accepted += 1
            if self._accepted == self._wtct_num_subtasks:
                self._reset()

    def reject(self):
        with self._lock:
            self._rejected += 1
            self._reset()

    def cancel(self):
        with self._lock:
            self._started = max(self._started - 1, 0)

    def rejected(self):
        with self._lock:
            if self._rejected:
                logger.warning('%s has rejected subtask', self._wtct_hash)
                return True

            return False

    def should_wait(self, wtct_hash: Optional[bytes] = None):
        with self._lock:
            if self._wtct_hash is not None:
                if self._wtct_hash != wtct_hash:
                    logger.warning('already processing another WTCT (%s vs %s)',
                                   self._wtct_hash, wtct_hash)
                    return True

                if self._started == self._wtct_num_subtasks:
                    logger.warning('all subtasks for %s have been started',
                                   self._wtct_hash)
                    return True

            return False
