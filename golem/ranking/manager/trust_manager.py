from golem.ranking.helper.min_max_utility import count_trust
from golem.ranking.helper.trust_const import UNKNOWN_TRUST, NEIGHBOUR_WEIGHT_BASE, NEIGHBOUR_WEIGHT_POWER
from golem.ranking.manager.database_manager import get_neighbour_loc_rank, get_local_rank


############
# computed #
############
def __computed_trust_positive(rank):
    return rank.positive_computed


def __computed_trust_negative(rank):
    return rank.negative_computed + rank.wrong_computed


def computed_trust_local(local_rank):
    return count_trust(__computed_trust_positive(local_rank), __computed_trust_negative(local_rank)) \
        if local_rank is not None else None


def computed_node_trust_local(node_id):
    return computed_trust_local(get_local_rank(node_id))


def __computed_neighbour_trust_local(neighbour, about):
    rank = get_neighbour_loc_rank(neighbour, about)
    return rank.computing_trust_value if rank is not None else UNKNOWN_TRUST


def __computed_neighbour_weight(node_id):
    local_trust = computed_node_trust_local(node_id)
    return NEIGHBOUR_WEIGHT_BASE ** (NEIGHBOUR_WEIGHT_POWER * local_trust) \
        if local_trust is not None else NEIGHBOUR_WEIGHT_BASE ** (NEIGHBOUR_WEIGHT_POWER * UNKNOWN_TRUST)


def computed_neighbours_rank(node_id, neighbours):
    sum_weight = 0.0
    sum_trust = 0.0
    for neighbour in [x for x in neighbours if x != node_id]:
        trust = __computed_neighbour_trust_local(neighbour, node_id)
        weight = __requested_neighbour_weight(neighbour)
        sum_trust += (weight - 1) * trust
        sum_weight += weight
    return sum_trust, sum_weight


#############
# requested #
#############
def __requested_trust_positive(rank):
    return rank.positive_payment


def __requested_trust_negative(rank):
    return rank.negative_requested + rank.negative_payment


def requested_trust_local(local_rank):
    return count_trust(__requested_trust_positive(local_rank), __requested_trust_negative(local_rank)) \
        if local_rank is not None else None


def requested_node_trust_local(node_id):
    return requested_trust_local(get_local_rank(node_id))


def __requested_neighbour_trust_local(neighbour, about):
    rank = get_neighbour_loc_rank(neighbour, about)
    return rank.requesting_trust_value if rank is not None else UNKNOWN_TRUST


def __requested_neighbour_weight(node_id):
    local_trust = requested_node_trust_local(node_id)
    return NEIGHBOUR_WEIGHT_BASE ** (NEIGHBOUR_WEIGHT_POWER * local_trust) \
        if local_trust is not None else NEIGHBOUR_WEIGHT_BASE ** (NEIGHBOUR_WEIGHT_POWER * UNKNOWN_TRUST)


def requested_neighbours_rank(node_id, neighbours):
    sum_weight = 0.0
    sum_trust = 0.0
    for neighbour in [x for x in neighbours if x != node_id]:
        trust = __requested_neighbour_trust_local(neighbour, node_id)
        weight = __computed_neighbour_weight(neighbour)
        sum_trust += (weight - 1) * trust
        sum_weight += weight
    return sum_trust, sum_weight
