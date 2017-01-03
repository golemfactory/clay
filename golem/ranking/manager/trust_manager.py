from golem.ranking.helper.min_max_utility import count_trust
from golem.ranking.helper.trust_const import UNKNOWN_TRUST
from golem.ranking.manager.database_manager import get_neighbour_loc_rank, get_local_rank


def __computed_trust_positive(rank):
    return rank.positive_computed


def __computed_trust_negative(rank):
    return rank.negative_computed + rank.wrong_computed


def computed_trust_local(local_rank):
    return count_trust(__computed_trust_positive(local_rank), __computed_trust_negative(local_rank)) \
        if local_rank is not None else None


def computed_node_trust_local(node_id):
    return computed_trust_local(get_local_rank(node_id))


def computed_neighbour_trust_local(neighbour, about):
    rank = get_neighbour_loc_rank(neighbour, about)
    return rank.computing_trust_value if rank is not None else UNKNOWN_TRUST


def __requested_trust_positive(rank):
    return rank.positive_payment


def __requested_trust_negative(rank):
    return rank.negative_requested + rank.negative_payment


def requested_trust_local(local_rank):
    return count_trust(__requested_trust_positive(local_rank), __requested_trust_negative(local_rank)) \
        if local_rank is not None else None


def requested_node_trust_local(node_id):
    return requested_trust_local(get_local_rank(node_id))


def requested_neighbour_trust_local(neighbour, about):
    rank = get_neighbour_loc_rank(neighbour, about)
    return rank.requesting_trust_value if rank is not None else UNKNOWN_TRUST
