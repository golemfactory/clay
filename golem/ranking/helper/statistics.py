from enum import Enum
from golem.ranking.manager import database_manager as dm


class Statistics(Enum):
    COMPUTED = {
        'increase': dm.increase_positive_computing,
        'decrease': dm.increase_negative_computing
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
