import logging

POS_PAR = 1.0
NEG_PAR = 2.0
MAX_TRUST = 1.0
MIN_TRUST = -1.0
MIN_OP_NUM = 50

logger = logging.getLogger(__name__)


def count_trust(pos, neg):
    return min(MAX_TRUST, max(MIN_TRUST, (pos * POS_PAR - neg * NEG_PAR) / max(pos + neg, MIN_OP_NUM)))


def vec_to_trust(val):
    if val is None:
        return 0.0
    try:
        a, b = val
    except (ValueError, TypeError) as err:
        logger.warning("Wrong trust vector element {}".format(err))
        return None
    return min(MAX_TRUST, max(MIN_TRUST, float(a) / float(b))) if a != 0.0 and b != 0.0 else 0.0
