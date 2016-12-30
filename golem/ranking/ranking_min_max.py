import logging
import operator
import random
from itertools import izip
from threading import Lock

from golem.ranking.helper.ranking_stats import RankingStats
from golem.ranking.helper.time_management import DiscreteTimeRoundOracle
from twisted.internet.task import deferLater

from golem.ranking.helper.ranking_database import RankingDatabase

logger = logging.getLogger(__name__)

POS_PAR = 1.0
NEG_PAR = 2.0
MAX_TRUST = 1.0
MIN_TRUST = -1.0
UNKNOWN_TRUST = 0.0
MIN_OP_NUM = 50
MAX_STEPS = 10
EPSILON = 0.01
LOC_RANK_PUSH_DELTA = 0.1


class Ranking(object):
    def __init__(self, client, pos_par=POS_PAR, neg_par=NEG_PAR, max_trust=MAX_TRUST, min_trust=MIN_TRUST,
                 min_op_num=MIN_OP_NUM, unknown_trust=UNKNOWN_TRUST, max_steps=MAX_STEPS, epsilon=EPSILON,
                 loc_rank_push_delta=LOC_RANK_PUSH_DELTA):
        self.db = RankingDatabase()
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
        self.lock = Lock()

    def run(self, reactor):
        self.reactor = reactor
        deferLater(self.reactor, self.round_oracle.sec_to_new_stage(), self.__init_stage)

    def __init_stage(self):
        try:
            logger.debug("New gossip stage")
            self.__push_local_ranks()
            self.finished = False
            self.global_finished = False
            self.step = 0
            self.finished_neighbours = set()
            self.__init_working_vec()
        finally:
            deferLater(self.reactor, self.round_oracle.sec_to_round(), self.__new_round)

    def __init_working_vec(self):
        with self.lock:
            self.working_vec = {}
            self.prevRank = {}
            for loc_rank in self.db.get_all_local_rank():
                comp_trust = self.__count_trust(self.__get_comp_trust_pos(loc_rank),
                                                self.__get_comp_trust_neg(loc_rank))
                req_trust = self.__count_trust(self.__get_req_trust_pos(loc_rank), self.__get_req_trust_neg(loc_rank))
                self.working_vec[loc_rank.node_id] = [[comp_trust, 1.0], [req_trust, 1.0]]
                self.prevRank[loc_rank.node_id] = [comp_trust, req_trust]

    def __new_round(self):
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
            deferLater(self.reactor, self.round_oracle.sec_to_end_round(), self.__end_round)

    def __end_round(self):
        logger.debug("End gossip round")
        try:
            self.received_gossip = self.client.collect_gossip() + self.received_gossip
            self.__make_prev_rank()
            self.working_vec = {}
            self.__add_gossip()
            self.__check_finished()
        finally:
            deferLater(self.reactor, self.round_oracle.sec_to_break(), self.__make_break)

    def __make_break(self):
        logger.debug("Gossip round finished")
        try:
            self.__check_global_finished()
        except Exception:
            deferLater(self.reactor, self.round_oracle.sec_to_round(), self.__new_round)
            raise

        if self.global_finished:
            try:
                self.client.collect_gossip()
                self.client.collect_stopped_peers()
                self.__save_working_vec()
            finally:
                deferLater(self.reactor, self.round_oracle.sec_to_new_stage(), self.__init_stage)
        else:
            deferLater(self.reactor, self.round_oracle.sec_to_round(), self.__new_round)

    # thread-safe
    def increase_trust(self, node_id, stat, mod):
        with self.lock:
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
        with self.lock:
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

    def get_computing_trust(self, node_id):
        local_rank = self.__get_loc_computing_trust(node_id)
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

    def get_requesting_trust(self, node_id):
        local_rank = self.__get_loc_requesting_trust(node_id)
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

    def sync_network(self):
        neighbours_loc_ranks = self.client.collect_neighbours_loc_ranks()
        for [neighbour_id, about_id, loc_rank] in neighbours_loc_ranks:
            with self.lock:
                self.db.insert_or_update_neighbour_loc_rank(neighbour_id,
                                                            about_id, loc_rank)

    def __get_loc_computing_trust(self, node_id):
        local_rank = self.db.get_local_rank(node_id)
        # for known node
        return self.__count_trust(self.__get_comp_trust_pos(local_rank), self.__get_comp_trust_neg(local_rank)) \
            if local_rank is not None else None

    def __get_loc_requesting_trust(self, node_id):
        local_rank = self.db.get_local_rank(node_id)
        # for known node
        return self.__count_trust(self.__get_req_trust_pos(local_rank), self.__get_req_trust_neg(local_rank)) \
            if local_rank is not None else None

    def __get_computing_neighbour_loc_trust(self, neighbour, about):
        rank = self.db.get_neighbour_loc_rank(neighbour, about)
        return rank.computing_trust_value if rank is not None else self.unknown_trust

    def __get_requesting_neighbour_loc_trust(self, neighbour, about):
        rank = self.db.get_neighbour_loc_rank(neighbour, about)
        return rank.requesting_trust_value if rank is not None else self.unknown_trust

    @staticmethod
    def __neighbour_weight_base():
        return 2

    @staticmethod
    def __neighbour_weight_power():
        return 2

    def __count_neighbour_weight(self, node_id, computing=True):
        if computing:
            loc_trust = self.__get_loc_computing_trust(node_id)
        else:
            loc_trust = self.__get_loc_requesting_trust(node_id)
        if loc_trust is None:
            loc_trust = self.unknown_trust
        return self.__neighbour_weight_base() ** (self.__neighbour_weight_power() * loc_trust)

    def __push_local_ranks(self):
        for loc_rank in self.db.get_all_local_rank():
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
            self.global_finished = set(self.neighbours) <= self.finished_neighbours

    def __compare_working_vec_and_prev_rank(self):
        aggregated_trust = 0.0
        for node_id, val in self.working_vec.items():
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
            aggregated_trust += abs(comp_trust - comp_trust_old) + abs(req_trust - req_trust_old)
        return aggregated_trust

    def __count_trust(self, pos, neg):
        val = pos * self.pos_par - neg * self.neg_par
        val /= max(pos + neg, self.min_op_num)
        val = min(self.max_trust, max(self.min_trust, val))
        return val

    def __set_k(self):
        degrees = self.__get_neighbours_degree()
        degree = len(degrees)
        if degree == 0:
            self.k = 0
        else:
            sum_degrees = sum(degrees.values())
            avg = float(sum_degrees) / float(degree)
            self.k = max(int(round(float(degree) / avg)), 1)

    def __get_neighbours_degree(self):
        degrees = self.client.get_neighbours_degree()
        self.neighbours = degrees.keys()
        return degrees

    def __make_prev_rank(self):
        for node_id, val in self.working_vec.items():
            try:
                computing, requesting = val
            except (TypeError, ValueError):
                logger.warning("Wrong trust vector element {}".format(val))
                break
            comp_trust = self.__working_vec_to_trust(computing)
            req_trust = self.__working_vec_to_trust(requesting)
            self.prevRank[node_id] = [comp_trust, req_trust]

    def __save_working_vec(self):
        for node_id, val in self.working_vec.items():
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
        for node_id, val in self.working_vec.items():
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

    @staticmethod
    def __sum_gossip(a, b):
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
                    trust = self.__get_computing_neighbour_loc_trust(n, node_id)
                else:
                    trust = self.__get_requesting_neighbour_loc_trust(n, node_id)
                weight = self.__count_neighbour_weight(n, not computing)
                sum_trust += (weight - 1) * trust
                sum_weight += weight
        return sum_trust, sum_weight

    @staticmethod
    def __get_comp_trust_pos(rank):
        return rank.positive_computed

    @staticmethod
    def __get_comp_trust_neg(rank):
        return rank.negative_computed + rank.wrong_computed

    @staticmethod
    def __get_req_trust_pos(rank):
        return rank.positive_payment

    @staticmethod
    def __get_req_trust_neg(rank):
        return rank.negative_requested + rank.negative_payment
