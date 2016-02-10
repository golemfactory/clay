import logging
import time
import random
import operator
import datetime

from twisted.internet.task import deferLater
from itertools import izip
from peewee import IntegrityError

from golem.model import LocalRank, GlobalRank, NeighbourLocRank
from golem.core.variables import BREAK_TIME, ROUND_TIME, END_ROUND_TIME, STAGE_TIME


logger = logging.getLogger(__name__)


class RankingStats(object):
    computed = "computed"
    wrong_computed = "wrong_computed"
    requested = "requested"
    payment = "payment"
    resource = "resource"


class RankingDatabase:
    def __init__(self, database):
        self.db = database.db

    def increase_positive_computing(self, node_id, trust_mod):
        try:
            with self.db.transaction():
                LocalRank.create(node_id=node_id, positive_computed=trust_mod)
        except IntegrityError:
            LocalRank.update(positive_computed=LocalRank.positive_computed + trust_mod,
                             modified_date=str(datetime.datetime.now())).where(LocalRank.node_id == node_id).execute()

    def increase_negative_computing(self, node_id, trust_mod):
        try:
            with self.db.transaction():
                LocalRank.create(node_id=node_id, negative_computed=trust_mod)
        except IntegrityError:
            LocalRank.update(negative_computed=LocalRank.negative_computed + trust_mod,
                             modified_date=str(datetime.datetime.now())).where(LocalRank.node_id == node_id).execute()

    def increase_wrong_computed(self, node_id, trust_mod):
        try:
            with self.db.transaction():
                LocalRank.create(node_id=node_id, wrong_computed=trust_mod)
        except IntegrityError:
            LocalRank.update(wrong_computed=LocalRank.wrong_computed + trust_mod,
                             modified_date=str(datetime.datetime.now())).where(LocalRank.node_id == node_id).execute()

    def increase_positive_requested(self, node_id, trust_mod):
        try:
            with self.db.transaction():
                LocalRank.create(node_id=node_id, positive_requested=trust_mod)
        except IntegrityError:
            LocalRank.update(positive_requested=LocalRank.positive_requested + trust_mod,
                             modified_date=str(datetime.datetime.now())).where(LocalRank.node_id == node_id).execute()

    def increase_negative_requested(self, node_id, trust_mod):
        try:
            with self.db.transaction():
                LocalRank.create(node_id=node_id, negative_requested=trust_mod)
        except IntegrityError:
            LocalRank.update(negative_requested=LocalRank.negative_requested + trust_mod,
                             modified_date=str(datetime.datetime.now())).where(LocalRank.node_id == node_id).execute()

    def increase_positive_payment(self, node_id, trust_mod):
        try:
            with self.db.transaction():
                LocalRank.create(node_id=node_id, positive_payment=trust_mod)
        except IntegrityError:
            LocalRank.update(positive_payment=LocalRank.positive_payment + trust_mod,
                             modified_date=str(datetime.datetime.now())).where(LocalRank.node_id == node_id).execute()

    def increase_negative_payment(self, node_id, trust_mod):
        try:
            with self.db.transaction():
                LocalRank.create(node_id=node_id, negative_payment=trust_mod)
        except IntegrityError:
            LocalRank.update(negative_payment=LocalRank.negative_payment + trust_mod,
                             modified_date=str(datetime.datetime.now())).where(LocalRank.node_id == node_id).execute()

    def increase_positive_resource(self, node_id, trust_mod):
        try:
            with self.db.transaction():
                LocalRank.create(node_id=node_id, positive_resource=trust_mod)
        except IntegrityError:
            LocalRank.update(positive_resource=LocalRank.positive_resource + trust_mod,
                             modified_date=str(datetime.datetime.now())).where(LocalRank.node_id == node_id).execute()

    def increase_negative_resource(self, node_id, trust_mod):
        try:
            with self.db.transaction():
                LocalRank.create(node_id=node_id, negative_resource=trust_mod)
        except IntegrityError:
            LocalRank.update(positive_resource=LocalRank.negative_resource + trust_mod,
                             modified_date=str(datetime.datetime.now())).where(LocalRank.node_id == node_id).execute()

    def get_local_rank(self, node_id):
        return LocalRank.select().where(LocalRank.node_id == node_id).first()

    def get_global_rank(self, node_id):
        return GlobalRank.select().where(GlobalRank.node_id == node_id).first()

    def insert_or_update_global_rank(self, node_id, comp_trust, req_trust, comp_weight, req_weight):
        try:
            with self.db.transaction():
                GlobalRank.create(node_id=node_id, requesting_trust_value=req_trust, computing_trust_value=comp_trust,
                                  gossip_weight_computing=comp_weight, gossip_weight_requesting=req_weight)
        except IntegrityError:
            GlobalRank.update(requesting_trust_value=req_trust, computing_trust_value=comp_trust,
                              gossip_weight_computing=comp_weight, gossip_weight_requesting=req_weight,
                              modified_date=str(datetime.datetime.now())).where(GlobalRank.node_id == node_id).execute()

    def get_all_local_rank(self):
        return LocalRank.select()

    def insert_or_update_neighbour_loc_rank(self, neighbour_id, about_id, loc_rank):
        try:
            if neighbour_id == about_id:
                logger.warning("Removing {} selftrust".format(about_id))
                return
            with self.db.transaction():
                NeighbourLocRank.create(node_id=neighbour_id, about_node_id=about_id,
                                        requesting_trust_value=loc_rank[1], computing_trust_value=loc_rank[0])
        except IntegrityError:
            NeighbourLocRank.update(requesting_trust_value=loc_rank[1], computing_trust_value=loc_rank[0]).where(
                    (NeighbourLocRank.about_node_id == about_id) & (NeighbourLocRank.node_id == neighbour_id)).execute()

    def get_neighbour_loc_rank(self, neighbour_id, about_id):
        return NeighbourLocRank.select().where(
                (NeighbourLocRank.node_id == neighbour_id) & (NeighbourLocRank.about_node_id == about_id)).first()


POS_PAR = 1.0
NEG_PAR = 2.0
MAX_TRUST = 1.0
MIN_TRUST = -1.0
UNKNOWN_TRUST = 0.0
MIN_OP_NUM = 50
MAX_STEPS = 10
EPSILON = 0.01
LOC_RANK_PUSH_DELTA = 0.1


class Ranking:
    def __init__(self, client, database, pos_par=POS_PAR, neg_par=NEG_PAR, max_trust=MAX_TRUST, min_trust=MIN_TRUST,
                 min_op_num=MIN_OP_NUM, unknown_trust=UNKNOWN_TRUST, max_steps=MAX_STEPS, epsilon=EPSILON,
                 loc_rank_push_delta=LOC_RANK_PUSH_DELTA):
        self.db = database
        self.client = client
        self.pos_par = pos_par
        self.neg_par = neg_par
        self.max_trust = max_trust
        self.min_trust = min_trust
        self.unknown_trust = unknown_trust
        self.min_op_num = min_op_num
        self.round_oracle = DiscreteTimeRoundOracle()

        self.k = 1
        self.epsilon = epsilon
        self.neighbours = []
        self.step = 0
        self.max_steps = max_steps
        self.working_vec = {}
        self.prevRank = {}
        self.globRank = {}
        self.received_gossip = []
        self.finished = False
        self.finished_neighbours = set()
        self.global_finished = False
        self.reactor = None
        self.initLocRankPush = True
        self.prev_loc_rank = {}
        self.loc_rank_push_delta = loc_rank_push_delta

    def run(self, reactor):
        self.reactor = reactor
        deferLater(self.reactor, self.round_oracle.sec_to_new_stage(), self.init_stage)

    def init_stage(self):
        try:
            logger.debug("New gossip stage")
            self.__push_local_ranks()
            self.finished = False
            self.global_finished = False
            self.step = 0
            self.finished_neighbours = set()
            self.init_working_vec()
        finally:
            deferLater(self.reactor, self.round_oracle.sec_to_round(), self.new_round)

    def init_working_vec(self):
        self.working_vec = {}
        self.prevRank = {}
        for loc_rank in self.db.get_all_local_rank():
            comp_trust = self.__count_trust(self.__get_comp_trust_pos(loc_rank), self.__get_comp_trust_neg(loc_rank))
            req_trust = self.__count_trust(self.__get_req_trust_pos(loc_rank), self.__get_req_trust_neg(loc_rank))
            self.working_vec[loc_rank.node_id] = [[comp_trust, 1.0], [req_trust, 1.0]]
            self.prevRank[loc_rank.node_id] = [comp_trust, req_trust]

    def new_round(self):
        logger.debug("New gossip round")
        try:
            self.__set_k()
            self.step += 1
            gossip = self.__prepare_gossip()
            if len(self.neighbours) > 0:
                send_to = random.sample(self.neighbours, self.k)
                self.client.send_gossip(gossip, send_to)
            self.received_gossip = [gossip]
        finally:
            deferLater(self.reactor, self.round_oracle.sec_to_end_round(), self.end_round)

    def end_round(self):
        logger.debug("End gossip round")
        try:
            self.received_gossip = self.client.collect_gossip() + self.received_gossip
            self.__make_prev_rank()
            self.working_vec = {}
            self.__add_gossip()
            self.__check_finished()
        finally:
            deferLater(self.reactor, self.round_oracle.sec_to_break(), self.make_break)

    def make_break(self):
        logger.debug("Gossip round finished")
        try:
            self.__check_global_finished()
        except Exception:
            deferLater(self.reactor, self.round_oracle.sec_to_round(), self.new_round)
            raise

        if self.global_finished:
            try:
                self.client.collect_gossip()
                self.client.collect_stopped_peers()
                self.__save_working_vec()
            finally:
                deferLater(self.reactor, self.round_oracle.sec_to_new_stage(), self.init_stage)
        else:
            deferLater(self.reactor, self.round_oracle.sec_to_round(), self.new_round)

    def increase_trust(self, node_id, stat, mod):
        if stat == RankingStats.computed:
            self.db.increase_positive_computing(node_id, mod)
        elif stat == RankingStats.requested:
            self.db.increase_positive_requested(node_id, mod)
        elif stat == RankingStats.payment:
            self.db.increase_positive_payment(node_id, mod)
        elif stat == RankingStats.resource:
            self.db.increase_positive_resource(node_id, mod)
        else:
            logger.error("Wrong stat type {}".format(stat))

    def decrease_trust(self, node_id, stat, mod):
        if stat == RankingStats.computed:
            self.db.increase_negative_computing(node_id, mod)
        elif stat == RankingStats.wrong_computed:
            self.db.increase_wrong_computed(node_id, mod)
        elif stat == RankingStats.requested:
            self.db.increase_negative_requested(node_id, mod)
        elif stat == RankingStats.payment:
            self.db.increase_negative_payment(node_id, mod)
        elif stat == RankingStats.resource:
            self.db.increase_negative_resource(node_id, mod)
        else:
            logger.error("Wrong stat type {}".format(stat))

    def get_loc_computing_trust(self, node_id):
        local_rank = self.db.get_local_rank(node_id)
        # Known node
        if local_rank is not None:
            return self.__count_trust(self.__get_comp_trust_pos(local_rank), self.__get_comp_trust_neg(local_rank))
        return None

    def get_computing_trust(self, node_id):
        local_rank = self.get_loc_computing_trust(node_id)
        if local_rank is not None:
            logger.debug("Using local rank {}".format(local_rank))
            return local_rank
        rank, weight_sum = self.__count_neighbours_rank(node_id, computing=True)
        global_rank = self.db.get_global_rank(node_id)
        if global_rank is not None:
            if weight_sum + global_rank.gossip_weight_computing != 0:
                logger.debug("Using gossipRank + neighboursRank")
                return (rank + global_rank.computing_trust_value) / (weight_sum + global_rank.gossip_weight_computing)
        elif weight_sum != 0:
            logger.debug("Using neighboursRank")
            return rank / float(weight_sum)
        return self.unknown_trust

    def get_loc_requesting_trust(self, node_id):
        local_rank = self.db.get_local_rank(node_id)
        # Known node
        if local_rank is not None:
            return self.__count_trust(self.__get_req_trust_pos(local_rank), self.__get_req_trust_neg(local_rank))
        return None

    def get_requesting_trust(self, node_id):
        local_rank = self.get_loc_requesting_trust(node_id)
        if local_rank is not None:
            logger.debug("Using local rank {}".format(local_rank))
            return local_rank
        rank, weight_sum = self.__count_neighbours_rank(node_id, computing=False)
        global_rank = self.db.get_global_rank(node_id)
        if global_rank is not None:
            if global_rank.gossip_weight_requesting != 0:
                logger.debug("Using gossipRank + neighboursRank")
                return (rank + global_rank.requesting_trust_value) / float(
                    weight_sum + global_rank.gossip_weight_requesting)
        elif weight_sum != 0:
            logger.debug("Using neighboursRank")
            return rank / float(weight_sum)

        return self.unknown_trust

    def get_computing_neighbour_loc_trust(self, neighbour, about):
        rank = self.db.get_neighbour_loc_rank(neighbour, about)
        if rank is not None:
            return rank.computing_trust_value
        return self.unknown_trust

    def get_requesting_neighbour_loc_trust(self, neighbour, about):
        rank = self.db.get_neighbour_loc_rank(neighbour, about)
        if rank is not None:
            return rank.requesting_trust_value
        return self.unknown_trust

    def neighbour_weight_base(self):
        return 2

    def neighbour_weight_power(self, node_id):
        return 2

    def count_neighbour_weight(self, node_id, computing=True):
        if computing:
            loc_trust = self.get_loc_computing_trust(node_id)
        else:
            loc_trust = self.get_loc_requesting_trust(node_id)
        if loc_trust is None:
            loc_trust = self.unknown_trust
        return self.neighbour_weight_base() ** (self.neighbour_weight_power(node_id) * loc_trust)

    def sync_network(self):
        neighbours_loc_ranks = self.client.collect_neighbours_loc_ranks()
        for [neighbour_id, about_id, loc_rank] in neighbours_loc_ranks:
            self.db.insert_or_update_neighbour_loc_rank(neighbour_id,
                                                        about_id, loc_rank)

    def __push_local_ranks(self):
        for loc_rank in self.db.get_all_local_rank():
            if loc_rank.node_id in self.prev_loc_rank:
                prev_trust = self.prev_loc_rank[loc_rank.node_id]

            comp_trust = self.__count_trust(self.__get_comp_trust_pos(loc_rank), self.__get_comp_trust_neg(loc_rank))
            req_trust = self.__count_trust(self.__get_req_trust_pos(loc_rank), self.__get_req_trust_neg(loc_rank))
            trust = [comp_trust, req_trust]
            if loc_rank.node_id in self.prev_loc_rank:
                prev_trust = self.prev_loc_rank[loc_rank.node_id]
            else:
                prev_trust = [float("inf")] * 2
            if max(map(abs, map(operator.sub, prev_trust, trust))) > self.loc_rank_push_delta:
                self.client.push_local_rank(loc_rank.node_id, trust)
                self.prev_loc_rank[loc_rank.node_id] = trust

    def __check_finished(self):
        if self.global_finished:
            return
        if not self.finished:
            if self.step >= self.max_steps:
                self.finished = True
                self.__send_finished()
            else:
                val = self.__compare_working_vec_and_prev_rank()
                if val <= len(self.working_vec) * self.epsilon * 2:
                    self.finished = True
                    self.__send_finished()

    def __check_global_finished(self):
        self.__mark_finished(self.client.collect_stopped_peers())
        if self.finished:
            self.global_finished = True
            for n in self.neighbours:
                if n not in self.finished_neighbours:
                    self.global_finished = False
                    break

    def __compare_working_vec_and_prev_rank(self):
        sum = 0.0
        for node_id, val in self.working_vec.iteritems():
            try:
                computing, requesting = val
            except (TypeError, ValueError):
                logger.warning("Wrong trust vector element {}".format(val))
                break
            comp_trust = self.__working_vec_to_trust(computing)
            req_trust = self.__working_vec_to_trust(requesting)
            if node_id in self.prevRank:
                comp_trust_old = self.prevRank[node_id][0]
                req_trust_old = self.prevRank[node_id][1]
            else:
                comp_trust_old, req_trust_old = 0, 0
            sum += abs(comp_trust - comp_trust_old) + abs(req_trust - req_trust_old)
        return sum

    def __count_trust(self, pos, neg):
        val = pos * self.pos_par - neg * self.neg_par
        val /= max(pos + neg, self.min_op_num)
        val = min(self.max_trust, max(self.min_trust, val))
        return val

    def __set_k(self):
        degrees = self.__get_neighbours_degree()
        sum_degrees = sum(degrees.itervalues())
        degree = len(degrees)
        if degree == 0:
            self.k = 0
        else:
            avg = float(sum_degrees) / float(degree)
            self.k = max(int(round(float(degree) / avg)), 1)

    def __get_neighbours_degree(self):
        degrees = self.client.get_neighbours_degree()
        self.neighbours = degrees.keys()
        return degrees

    def __make_prev_rank(self):
        for node_id, val in self.working_vec.iteritems():
            try:
                computing, requesting = val
            except (TypeError, ValueError):
                logger.warning("Wrong trust vector element {}".format(val))
                break
            comp_trust = self.__working_vec_to_trust(computing)
            req_trust = self.__working_vec_to_trust(requesting)
            self.prevRank[node_id] = [comp_trust, req_trust]

    def __save_working_vec(self):
        for node_id, val in self.working_vec.iteritems():
            try:
                computing, requesting = val
            except (TypeError, ValueError):
                logger.warning("Wrong trust vector element {}".format(val))
                break
            comp_trust = self.__working_vec_to_trust(computing)
            req_trust = self.__working_vec_to_trust(requesting)
            self.db.insert_or_update_global_rank(node_id, comp_trust, req_trust, computing[1], requesting[1])

    def __working_vec_to_trust(self, val):
        if val is None:
            return 0.0
        try:
            a, b = val
        except (ValueError, TypeError) as err:
            logger.warning("Wrong trust vector element {}".format(err))
            return None
        if a == 0.0 or b == 0.0:
            return 0.0
        else:
            return min(max(float(a) / float(b), self.min_trust), self.max_trust)

    def __prepare_gossip(self):
        gossip_vec = []
        for node_id, val in self.working_vec.iteritems():
            comp_trust = map(self.__scale_gossip, val[0])
            req_trust = map(self.__scale_gossip, val[1])
            gossip_vec.append([node_id, [comp_trust, req_trust]])
        return gossip_vec

    def __scale_gossip(self, val):
        return val / float(self.k + 1)

    def __add_gossip(self):
        for gossip_group in self.received_gossip:
            for gossip in gossip_group:
                try:
                    node_id, [comp, req] = gossip
                    if node_id in self.working_vec:
                        [prev_comp, prev_req] = self.working_vec[node_id]
                        self.working_vec[node_id] = [self.__sum_gossip(comp, prev_comp),
                                                     self.__sum_gossip(req, prev_req)]
                    else:
                        self.working_vec[node_id] = [comp, req]
                except Exception as err:
                    logger.error("Wrong gossip {}, {}".format(gossip, err))

        self.received_gossip = []

    def __sum_gossip(self, a, b):
        return map(sum, izip(a, b))

    def __send_finished(self):
        self.client.send_stop_gossip()

    def __mark_finished(self, finished):
        self.finished_neighbours |= finished

    def __count_neighbours_rank(self, node_id, computing):
        sum_weight = 0.0
        sum_trust = 0.0
        for n in self.neighbours:
            if n != node_id:
                if computing:
                    trust = self.get_computing_neighbour_loc_trust(n, node_id)
                else:
                    trust = self.get_requesting_neighbour_loc_trust(n, node_id)
                weight = self.count_neighbour_weight(n, not computing)
                sum_trust += (weight - 1) * trust
                sum_weight += weight
        return sum_trust, sum_weight

    def __get_comp_trust_pos(self, rank):
        return rank.positive_computed

    def __get_comp_trust_neg(self, rank):
        return rank.negative_computed + rank.wrong_computed

    def __get_req_trust_pos(self, rank):
        return rank.positive_payment

    def __get_req_trust_neg(self, rank):
        return rank.negative_requested + rank.negative_payment


class DiscreteTimeRoundOracle:
    def __init__(self, break_time=BREAK_TIME, round_time=ROUND_TIME, end_round_time=END_ROUND_TIME,
                 stage_time=STAGE_TIME):
        self.break_time = break_time
        self.round_time = round_time
        self.end_round_time = end_round_time
        self.stage_time = stage_time

    def __sum_time(self):
        return self.round_time + self.break_time + self.end_round_time

    def __time_mod(self):
        return time.time() % self.__sum_time()

    def is_break(self):
        return self.round_time + self.end_round_time < self.__time_mod()

    def is_round(self):
        return self.__time_mod() <= self.round_time

    def is_end_round(self):
        return self.round_time < self.__time_mod() <= self.round_time + self.end_round_time

    def sec_to_end_round(self):
        tm = self.__time_mod()
        if self.round_time - tm >= 0:
            return self.round_time - tm
        else:
            return self.__sum_time() + self.round_time - tm

    def sec_to_round(self):
        return self.__sum_time() - self.__time_mod()

    def sec_to_break(self):
        tm = self.__time_mod()
        if self.round_time + self.end_round_time - tm >= 0:
            return self.round_time + self.end_round_time - tm
        else:
            return self.__sum_time() + self.round_time + self.end_round_time - tm

    def sec_to_new_stage(self):
        return self.stage_time - time.time() % self.stage_time
