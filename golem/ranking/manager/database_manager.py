import datetime
import logging

from peewee import IntegrityError

from golem.model import LocalRank, GlobalRank, NeighbourLocRank, db
from golem.ranking import ProviderEfficacy
from golem.task.taskstate import SubtaskOp

logger = logging.getLogger(__name__)


REQUESTOR_FORGETTING_FACTOR = 0.9
PROVIDER_FORGETTING_FACTOR = 0.9


def increase_positive_computed(node_id, trust_mod):
    logger.debug('increase_positive_computed. node_id=%r, trust_mod=%r',
                 node_id, trust_mod)
    try:
        with db.transaction():
            LocalRank.create(node_id=node_id, positive_computed=trust_mod)
    except IntegrityError:
        LocalRank.update(positive_computed=LocalRank.positive_computed + trust_mod,
                         modified_date=str(datetime.datetime.now())) \
            .where(LocalRank.node_id == node_id).execute()


def increase_negative_computed(node_id, trust_mod):
    logger.debug('increase_negative_computed. node_id=%r, trust_mod=%r',
                 node_id, trust_mod)
    try:
        with db.transaction():
            LocalRank.create(node_id=node_id, negative_computed=trust_mod)
    except IntegrityError:
        LocalRank.update(negative_computed=LocalRank.negative_computed + trust_mod,
                         modified_date=str(datetime.datetime.now())) \
            .where(LocalRank.node_id == node_id).execute()


def increase_wrong_computed(node_id, trust_mod):
    logger.debug('increase_wrong_computed. node_id=%r, trust_mod=%r',
                 node_id, trust_mod)
    try:
        with db.transaction():
            LocalRank.create(node_id=node_id, wrong_computed=trust_mod)
    except IntegrityError:
        LocalRank.update(wrong_computed=LocalRank.wrong_computed + trust_mod,
                         modified_date=str(datetime.datetime.now())) \
            .where(LocalRank.node_id == node_id).execute()


def increase_positive_requested(node_id, trust_mod):
    logger.debug('increase_positive_requested. node_id=%r, trust_mod=%r',
                 node_id, trust_mod)
    try:
        with db.transaction():
            LocalRank.create(node_id=node_id, positive_requested=trust_mod)
    except IntegrityError:
        LocalRank.update(positive_requested=LocalRank.positive_requested + trust_mod,
                         modified_date=str(datetime.datetime.now())) \
            .where(LocalRank.node_id == node_id).execute()


def increase_negative_requested(node_id, trust_mod):
    logger.debug('increase_negative_requested. node_id=%r, trust_mod=%r',
                 node_id, trust_mod)
    try:
        with db.transaction():
            LocalRank.create(node_id=node_id, negative_requested=trust_mod)
    except IntegrityError:
        LocalRank.update(negative_requested=LocalRank.negative_requested + trust_mod,
                         modified_date=str(datetime.datetime.now())) \
            .where(LocalRank.node_id == node_id).execute()


def increase_positive_payment(node_id, trust_mod):
    logger.debug('increase_positive_payment. node_id=%r, trust_mod=%r',
                 node_id, trust_mod)
    try:
        with db.transaction():
            LocalRank.create(node_id=node_id, positive_payment=trust_mod)
    except IntegrityError:
        LocalRank.update(positive_payment=LocalRank.positive_payment + trust_mod,
                         modified_date=str(datetime.datetime.now())) \
            .where(LocalRank.node_id == node_id).execute()


def increase_negative_payment(node_id, trust_mod):
    logger.debug('increase_negative_payment. node_id=%r, trust_mod=%r',
                 node_id, trust_mod)
    try:
        with db.transaction():
            LocalRank.create(node_id=node_id, negative_payment=trust_mod)
    except IntegrityError:
        LocalRank.update(negative_payment=LocalRank.negative_payment + trust_mod,
                         modified_date=str(datetime.datetime.now())) \
            .where(LocalRank.node_id == node_id).execute()


def increase_positive_resource(node_id, trust_mod):
    logger.debug('increase_positive_resource. node_id=%r, trust_mod=%r',
                 node_id, trust_mod)
    try:
        with db.transaction():
            LocalRank.create(node_id=node_id, positive_resource=trust_mod)
    except IntegrityError:
        LocalRank.update(positive_resource=LocalRank.positive_resource + trust_mod,
                         modified_date=str(datetime.datetime.now())) \
            .where(LocalRank.node_id == node_id).execute()


def increase_negative_resource(node_id, trust_mod):
    logger.debug('increase_negative_resource. node_id=%r, trust_mod=%r',
                 node_id, trust_mod)
    try:
        with db.transaction():
            LocalRank.create(node_id=node_id, negative_resource=trust_mod)
    except IntegrityError:
        LocalRank.update(negative_resource=LocalRank.negative_resource + trust_mod,
                         modified_date=str(datetime.datetime.now())) \
            .where(LocalRank.node_id == node_id).execute()


def _calculate_efficiency(efficiency: float,
                          timeout: float,
                          computation_time: float,
                          psi: float) -> float:
    """
    Efficiency function from both Requestor and Provider perspective as
    proposed in https://docs.golem.network/About/img/Brass_Golem_Marketplace.pdf
    """
    if computation_time == 0.:
        raise ValueError("computation_time cannot be equal to 0.")

    v = timeout / computation_time
    return psi * efficiency + (1 - psi) * v


def get_requestor_efficiency(node_id: str) -> float:
    with db.transaction():
        rank, _ = LocalRank.get_or_create(node_id=node_id)
        efficiency = rank.requestor_efficiency
        return efficiency or 1.0


def update_requestor_efficiency(node_id: str,
                                timeout: float,
                                computation_time: float,
                                performance: float,
                                min_performance: float) -> None:
    """
    Update efficiency function from both Requestor and Provider perspective as
    proposed in https://docs.golem.network/About/img/Brass_Golem_Marketplace.pdf
    """
    with db.transaction():
        rank, _ = LocalRank.get_or_create(node_id=node_id)
        efficiency = rank.requestor_efficiency

        if efficiency is None:
            efficiency = (
                1. if not min_performance else
                performance / min_performance
            )

        rank.requestor_efficiency = _calculate_efficiency(
            efficiency, timeout, computation_time, REQUESTOR_FORGETTING_FACTOR)
        rank.save()


def get_requestor_assigned_sum(node_id: str) -> int:
    with db.transaction():
        rank, _ = LocalRank.get_or_create(node_id=node_id)
        return rank.requestor_assigned_sum or 0


def update_requestor_assigned_sum(node_id: str, amount: int) -> None:
    """
    V_assigned from Provider perspective as
    proposed in https://docs.golem.network/About/img/Brass_Golem_Marketplace.pdf
    """

    with db.transaction():
        rank, _ = LocalRank.get_or_create(node_id=node_id)
        rank.requestor_assigned_sum += amount
        if rank.requestor_assigned_sum < 0:
            logger.error('LocalRank.requestor_assigned_sum '
                         'unexpectedly negative, setting to 0. '
                         'node_id=%r', node_id)
            rank.requestor_assigned_sum = 0
        rank.save()


def update_requestor_paid_sum(node_id: str, amount: int) -> None:
    """
    V_paid from Provider perspective as
    proposed in https://docs.golem.network/About/img/Brass_Golem_Marketplace.pdf
    """

    with db.transaction():
        rank, _ = LocalRank.get_or_create(node_id=node_id)
        rank.requestor_paid_sum += amount
        rank.save()


def get_requestor_paid_sum(node_id: str) -> int:
    with db.transaction():
        rank, _ = LocalRank.get_or_create(node_id=node_id)
        return rank.requestor_paid_sum or 0


def get_provider_efficiency(node_id: str) -> float:
    with db.transaction():
        rank, _ = LocalRank.get_or_create(node_id=node_id)
        return rank.provider_efficiency


def update_provider_efficiency(node_id: str,
                               timeout: float,
                               computation_time: float) -> None:

    with db.transaction():
        rank, _ = LocalRank.get_or_create(node_id=node_id)
        efficiency = rank.provider_efficiency

        rank.provider_efficiency = _calculate_efficiency(
            efficiency, timeout, computation_time, PROVIDER_FORGETTING_FACTOR)
        rank.save()


def get_provider_efficacy(node_id: str) -> ProviderEfficacy:
    with db.transaction():
        rank, _ = LocalRank.get_or_create(node_id=node_id)
        return rank.provider_efficacy


def update_provider_efficacy(node_id: str, op: SubtaskOp) -> None:

    with db.transaction():
        rank, _ = LocalRank.get_or_create(node_id=node_id)
        rank.provider_efficacy.update(op)
        rank.save()


def get_global_rank(node_id):
    return GlobalRank.select().where(GlobalRank.node_id == node_id).first()


def upsert_global_rank(node_id, comp_trust, req_trust, comp_weight, req_weight):
    try:
        with db.transaction():
            GlobalRank.create(node_id=node_id, requesting_trust_value=req_trust, computing_trust_value=comp_trust,
                              gossip_weight_computing=comp_weight, gossip_weight_requesting=req_weight)
    except IntegrityError:
        GlobalRank.update(requesting_trust_value=req_trust, computing_trust_value=comp_trust,
                          gossip_weight_computing=comp_weight, gossip_weight_requesting=req_weight,
                          modified_date=str(datetime.datetime.now())) \
            .where(GlobalRank.node_id == node_id).execute()


def get_local_rank(node_id):
    return LocalRank.select().where(LocalRank.node_id == node_id).first()


def get_local_rank_for_all():
    return LocalRank.select()


def get_neighbour_loc_rank(neighbour_id, about_id):
    return NeighbourLocRank.select().where(
        (NeighbourLocRank.node_id == neighbour_id) & (NeighbourLocRank.about_node_id == about_id)).first()


def upsert_neighbour_loc_rank(neighbour_id, about_id, loc_rank):
    try:
        if neighbour_id == about_id:
            logger.warning("Removing {} self trust".format(about_id))
            return
        with db.transaction():
            NeighbourLocRank.create(node_id=neighbour_id, about_node_id=about_id,
                                    requesting_trust_value=loc_rank[1], computing_trust_value=loc_rank[0])
    except IntegrityError:
        NeighbourLocRank.update(requesting_trust_value=loc_rank[1], computing_trust_value=loc_rank[0]) \
            .where(
            (NeighbourLocRank.about_node_id == about_id) & (NeighbourLocRank.node_id == neighbour_id)).execute()
