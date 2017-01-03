def computed_trust_positive(rank):
    return rank.positive_computed


def computed_trust_negative(rank):
    return rank.negative_computed + rank.wrong_computed


def requested_trust_positive(rank):
    return rank.positive_payment


def requested_trust_negative(rank):
    return rank.negative_requested + rank.negative_payment
