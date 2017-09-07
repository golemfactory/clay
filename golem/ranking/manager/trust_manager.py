from golem.ranking.helper.min_max_utility import count_trust
from golem.ranking.helper.trust_const import \
    UNKNOWN_TRUST, NEIGHBOUR_WEIGHT_BASE, NEIGHBOUR_WEIGHT_POWER
from golem.ranking.manager.database_manager \
    import get_neighbour_loc_rank, get_local_rank


def __neighbour_weight(local_trust):
    return NEIGHBOUR_WEIGHT_BASE ** (NEIGHBOUR_WEIGHT_POWER * local_trust) \
        if local_trust is not None \
        else \
        NEIGHBOUR_WEIGHT_BASE ** (NEIGHBOUR_WEIGHT_POWER * UNKNOWN_TRUST)


############
# computed #
############

def computed_trust_local(local_rank):
    return count_trust(
        local_rank.positive_computed,
        local_rank.negative_computed + local_rank.wrong_computed
    ) if local_rank is not None else None


def __computed_neighbour_trust_local(neighbour, about):
    rank = get_neighbour_loc_rank(neighbour, about)
    return rank.computing_trust_value if rank is not None else UNKNOWN_TRUST


def computed_neighbours_rank(node_id, neighbours):
    sum_weight = 0.0
    sum_trust = 0.0
    for neighbour in [x for x in neighbours if x != node_id]:
        neighbour_trust_to_node_id = \
            __computed_neighbour_trust_local(neighbour, node_id)
        trust_to_neighbour = computed_trust_local(get_local_rank(neighbour))
        weight = __neighbour_weight(trust_to_neighbour)
        sum_trust += (weight - 1) * neighbour_trust_to_node_id
        sum_weight += weight
    return sum_trust, sum_weight


#############
# requested #
#############

def requested_trust_local(local_rank):
    return count_trust(
        local_rank.positive_payment,
        local_rank.negative_requested + local_rank.negative_payment
    ) if local_rank is not None else None


def __requested_neighbour_trust_local(neighbour, about):
    rank = get_neighbour_loc_rank(neighbour, about)
    return rank.requesting_trust_value if rank is not None else UNKNOWN_TRUST


def requested_neighbours_rank(node_id, neighbours):
    sum_weight = 0.0
    sum_trust = 0.0
    for neighbour in [x for x in neighbours if x != node_id]:
        neighbour_trust_to_node_id = \
            __requested_neighbour_trust_local(neighbour, node_id)
        trust_to_neighbour = requested_trust_local(get_local_rank(neighbour))
        weight = __neighbour_weight(trust_to_neighbour)
        sum_trust += (weight - 1) * neighbour_trust_to_node_id
        sum_weight += weight
    return sum_trust, sum_weight
