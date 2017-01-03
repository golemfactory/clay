import logging

from golem.ranking.helper.trust_const import MAX_TRUST, MIN_TRUST

POS_WEIGHT = 1.0
NEG_WEIGHT = 2.0
MIN_OPERATION_NUMBER = 50

logger = logging.getLogger(__name__)


def count_trust(pos, neg):
    return min(MAX_TRUST, max(MIN_TRUST, (pos * POS_WEIGHT - neg * NEG_WEIGHT) / max(pos + neg, MIN_OPERATION_NUMBER)))


def vec_to_trust(val):
    if val is None:
        return 0.0
    try:
        a, b = val
    except (ValueError, TypeError) as err:
        logger.warning("Wrong trust vector element {}".format(err))
        return None
    return min(MAX_TRUST, max(MIN_TRUST, float(a) / float(b))) if a != 0.0 and b != 0.0 else 0.0
