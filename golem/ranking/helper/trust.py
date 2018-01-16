import logging

from threading import Lock
from enum import Enum
from golem.ranking.manager import database_manager as dm

logger = logging.getLogger(__name__)


class Trust(Enum):
    COMPUTED = {
        'increase': dm.increase_positive_computed,
        'decrease': dm.increase_negative_computed
    }
    WRONG_COMPUTED = {
        'decrease': dm.increase_wrong_computed
    }
    REQUESTED = {
        'increase': dm.increase_positive_requested,
        'decrease': dm.increase_negative_requested
    }
    PAYMENT = {
        'increase': dm.increase_positive_payment,
        'decrease': dm.increase_negative_payment
    }
    RESOURCE = {
        'increase': dm.increase_positive_resource,
        'decrease': dm.increase_negative_resource
    }

    def __init__(self, val):
        self.val = val
        self.lock = Lock()

    def increase(self, node_id, mod=1.0):
        with self.lock:
            try:
                self.val['increase'](node_id, mod)
            except KeyError:
                logger.error("Wrong key for stat type {}".format(self.val))
                raise

    def decrease(self, node_id, mod=1.0):
        with self.lock:
            self.val['decrease'](node_id, mod)
