import logging
import operator
import random
from itertools import izip
from threading import Lock

from twisted.internet.task import deferLater

from golem.ranking.helper import min_max_utility as util
from golem.ranking.helper.trust_const import UNKNOWN_TRUST
from golem.ranking.manager import database_manager as dm
from golem.ranking.manager import trust_manager as tm
from golem.ranking.manager.time_manager import TimeManager

logger = logging.getLogger(__name__)

MAX_STEPS = 10
EPSILON = 0.01
LOC_RANK_PUSH_DELTA = 0.1


class Ranking(object):
    def __init__(self, client, max_steps=MAX_STEPS, epsilon=EPSILON,
                 loc_rank_push_delta=LOC_RANK_PUSH_DELTA):
        self.client = client
        self.round_oracle = TimeManager()

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
            for loc_rank in dm.get_local_rank_for_all():
                comp_trust = tm.computed_trust_local(loc_rank)
                req_trust = tm.requested_trust_local(loc_rank)
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

    def get_computing_trust(self, node_id):
        local_trust = tm.computed_node_trust_local(node_id)
        if local_trust is not None:
            logger.debug("Using local rank {}".format(local_trust))
            return local_trust
        rank, weight_sum = tm.computed_neighbours_rank(node_id, self.neighbours)
        global_rank = dm.get_global_rank(node_id)
        if global_rank is not None:
            if weight_sum + global_rank.gossip_weight_computing != 0:
                logger.debug("Using gossipRank + neighboursRank")
                return (rank + global_rank.computing_trust_value) / float(
                    weight_sum + global_rank.gossip_weight_computing)
        elif weight_sum != 0:
            logger.debug("Using neighboursRank")
            return rank / float(weight_sum)
        return UNKNOWN_TRUST

    def get_requesting_trust(self, node_id):
        local_trust = tm.requested_node_trust_local(node_id)
        if local_trust is not None:
            logger.debug("Using local rank {}".format(local_trust))
            return local_trust
        rank, weight_sum = tm.requested_neighbours_rank(node_id, self.neighbours)
        global_rank = dm.get_global_rank(node_id)
        if global_rank is not None:
            if global_rank.gossip_weight_requesting != 0:
                logger.debug("Using gossipRank + neighboursRank")
                return (rank + global_rank.requesting_trust_value) / float(
                    weight_sum + global_rank.gossip_weight_requesting)
        elif weight_sum != 0:
            logger.debug("Using neighboursRank")
            return rank / float(weight_sum)
        return UNKNOWN_TRUST

    def sync_network(self):
        neighbours_loc_ranks = self.client.collect_neighbours_loc_ranks()
        for [neighbour_id, about_id, loc_rank] in neighbours_loc_ranks:
            with self.lock:
                dm.upsert_neighbour_loc_rank(neighbour_id, about_id, loc_rank)

    def __push_local_ranks(self):
        for loc_rank in dm.get_local_rank_for_all():
            comp_trust = tm.computed_trust_local(loc_rank)
            req_trust = tm.requested_trust_local(loc_rank)
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
            comp_trust = util.vec_to_trust(computing)
            req_trust = util.vec_to_trust(requesting)
            if node_id in self.prevRank:
                comp_trust_old = self.prevRank[node_id][0]
                req_trust_old = self.prevRank[node_id][1]
            else:
                comp_trust_old, req_trust_old = 0, 0
            aggregated_trust += abs(comp_trust - comp_trust_old) + abs(req_trust - req_trust_old)
        return aggregated_trust

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
            comp_trust = util.vec_to_trust(computing)
            req_trust = util.vec_to_trust(requesting)
            self.prevRank[node_id] = [comp_trust, req_trust]

    def __save_working_vec(self):
        for node_id, val in self.working_vec.items():
            try:
                computing, requesting = val
            except (TypeError, ValueError):
                logger.warning("Wrong trust vector element {}".format(val))
                break
            comp_trust = util.vec_to_trust(computing)
            req_trust = util.vec_to_trust(requesting)
            dm.upsert_global_rank(node_id, comp_trust, req_trust, computing[1], requesting[1])

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

