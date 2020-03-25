import logging
from threading import Lock
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class TaskClient(object):
    """
    Class for tracking single Provider (ie. task client). We allow single
    WantToComputeTask to be processed at once. Till it is not fully accepted
    no other WTCT can be started for the same Provider. It tracks how many
    subtasks with same WTCT hash has already been started not allowing more
    than declared. Upon subtask rejection it will get rejecting all subsequent
    starts (with any WTCT hash).
    """
    def __init__(self):
        self._lock: Lock = Lock()
        self._started: int = 0
        self._accepted: int = 0
        self._rejected: int = 0
        self._offer_hash: Optional[str] = None
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
        """ If given `node_id` is already in `node_dict` its corresponding
        `TaskClient` instance is returned; otherwise an empty `TaskClient` is
        inserted into `node_dict` and returned
        """
        if node_id not in node_dict:
            node_dict[node_id] = TaskClient()
        return node_dict[node_id]

    def _reset(self):
        self._started = 0
        self._accepted = 0
        self._offer_hash = None
        self._wtct_num_subtasks = 0

    def start(self, offer_hash: str, num_subtasks: int) -> bool:
        if self.should_wait(offer_hash) or self.rejected():
            return False

        with self._lock:
            self._offer_hash = offer_hash
            self._wtct_num_subtasks = num_subtasks
            self._started += 1

        return True

    def accept(self):
        with self._lock:
            self._accepted += 1
            if self._accepted == self._started:
                self._reset()

    def reject(self):
        with self._lock:
            self._rejected += 1
            self._reset()

    def cancel(self):
        with self._lock:
            self._started = max(self._started - 1, 0)
            if not self._started:
                self._reset()

    def rejected(self):
        with self._lock:
            if self._rejected:
                logger.info('`%s` has rejected subtask', self._offer_hash)
                return True

            return False

    def should_wait(self, offer_hash: str):
        with self._lock:
            if self._offer_hash is not None:
                if self._offer_hash != offer_hash:
                    logger.debug('already processing another offer (%s vs %s)',
                                 self._offer_hash, offer_hash)
                    return True

                if self._started == self._wtct_num_subtasks:
                    logger.info('all subtasks for `%s` have been started',
                                self._offer_hash)
                    return True

            return False
