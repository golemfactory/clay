import datetime
import logging

from peewee import IntegrityError

from golem.model import LocalRank, GlobalRank, NeighbourLocRank, db

logger = logging.getLogger(__name__)


def increase_positive_computed(node_id, trust_mod):
    try:
        with db.transaction():
            LocalRank.create(node_id=node_id, positive_computed=trust_mod)
    except IntegrityError:
        LocalRank.update(positive_computed=LocalRank.positive_computed + trust_mod,
                         modified_date=str(datetime.datetime.now())) \
            .where(LocalRank.node_id == node_id).execute()


def increase_negative_computed(node_id, trust_mod):
    try:
        with db.transaction():
            LocalRank.create(node_id=node_id, negative_computed=trust_mod)
    except IntegrityError:
        LocalRank.update(negative_computed=LocalRank.negative_computed + trust_mod,
                         modified_date=str(datetime.datetime.now())) \
            .where(LocalRank.node_id == node_id).execute()


def increase_wrong_computed(node_id, trust_mod):
    try:
        with db.transaction():
            LocalRank.create(node_id=node_id, wrong_computed=trust_mod)
    except IntegrityError:
        LocalRank.update(wrong_computed=LocalRank.wrong_computed + trust_mod,
                         modified_date=str(datetime.datetime.now())) \
            .where(LocalRank.node_id == node_id).execute()


def increase_positive_requested(node_id, trust_mod):
    try:
        with db.transaction():
            LocalRank.create(node_id=node_id, positive_requested=trust_mod)
    except IntegrityError:
        LocalRank.update(positive_requested=LocalRank.positive_requested + trust_mod,
                         modified_date=str(datetime.datetime.now())) \
            .where(LocalRank.node_id == node_id).execute()


def increase_negative_requested(node_id, trust_mod):
    try:
        with db.transaction():
            LocalRank.create(node_id=node_id, negative_requested=trust_mod)
    except IntegrityError:
        LocalRank.update(negative_requested=LocalRank.negative_requested + trust_mod,
                         modified_date=str(datetime.datetime.now())) \
            .where(LocalRank.node_id == node_id).execute()


def increase_positive_payment(node_id, trust_mod):
    try:
        with db.transaction():
            LocalRank.create(node_id=node_id, positive_payment=trust_mod)
    except IntegrityError:
        LocalRank.update(positive_payment=LocalRank.positive_payment + trust_mod,
                         modified_date=str(datetime.datetime.now())) \
            .where(LocalRank.node_id == node_id).execute()


def increase_negative_payment(node_id, trust_mod):
    try:
        with db.transaction():
            LocalRank.create(node_id=node_id, negative_payment=trust_mod)
    except IntegrityError:
        LocalRank.update(negative_payment=LocalRank.negative_payment + trust_mod,
                         modified_date=str(datetime.datetime.now())) \
            .where(LocalRank.node_id == node_id).execute()


def increase_positive_resource(node_id, trust_mod):
    try:
        with db.transaction():
            LocalRank.create(node_id=node_id, positive_resource=trust_mod)
    except IntegrityError:
        LocalRank.update(positive_resource=LocalRank.positive_resource + trust_mod,
                         modified_date=str(datetime.datetime.now())) \
            .where(LocalRank.node_id == node_id).execute()


def increase_negative_resource(node_id, trust_mod):
    try:
        with db.transaction():
            LocalRank.create(node_id=node_id, negative_resource=trust_mod)
    except IntegrityError:
        LocalRank.update(negative_resource=LocalRank.negative_resource + trust_mod,
                         modified_date=str(datetime.datetime.now())) \
            .where(LocalRank.node_id == node_id).execute()


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
