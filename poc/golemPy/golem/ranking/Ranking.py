import logging
import time
import random
import operator
import datetime

from twisted.internet.task import deferLater
from itertools import izip

logger = logging.getLogger(__name__)
from peewee import IntegrityError
from golem.Model import LocalRank, GlobalRank, NeighbourLocRank

class RankingStats:
    computed = "computed"
    wrongComputed = "wrongComputed"
    requested = "requested"
    payment = "payment"
    resource = "resource"

class RankingDatabase:
    def __init__(self, database):
        self.db = database.db

    ############################
    def increasePositiveComputing(self, node_id, trustMod):
        try:
            with self.db.transaction():
                LocalRank.create(node_id=node_id, positiveComputed=trustMod)
        except IntegrityError:
            LocalRank.update(positiveComputed = LocalRank.positiveComputed + trustMod, modified_date = str(datetime.datetime.now())).where(LocalRank.node_id == node_id).execute()

    ############################
    def increaseNegativeComputing(self, node_id, trustMod):
        try:
            with self.db.transaction():
                LocalRank.create(node_id = node_id, negativeComputed = trustMod)
        except IntegrityError:
            LocalRank.update(negativeComputed = LocalRank.negativeComputed + trustMod, modified_date = str(datetime.datetime.now())).where(LocalRank.node_id == node_id).execute()

    ############################
    def increaseWrongComputed(self, node_id, trustMod):
        try:
            with self.db.transaction():
                LocalRank.create(node_id = node_id, wrongComputed = trustMod)
        except IntegrityError:
            LocalRank.update(wrongComputed = LocalRank.wrongComputed + trustMod, modified_date = str(datetime.datetime.now())).where(LocalRank.node_id == node_id).execute()

    ############################
    def increasePositiveRequested(self, node_id, trustMod):
        try:
            with self.db.transaction():
                LocalRank.create(node_id=node_id, positiveRequested=trustMod)
        except IntegrityError:
            LocalRank.update(positiveRequested = LocalRank.positiveRequested + trustMod, modified_date = str(datetime.datetime.now())).where(LocalRank.node_id == node_id).execute()

    ############################
    def increaseNegativeRequested(self, node_id, trustMod):
        try:
            with self.db.transaction():
                LocalRank.create(node_id=node_id, negativeRequested=trustMod)
        except IntegrityError:
            LocalRank.update(negativeRequested = LocalRank.negativeRequested + trustMod, modified_date = str(datetime.datetime.now())).where(LocalRank.node_id == node_id).execute()

    ############################
    def increasePositivePayment(self, node_id, trustMod):
        try:
            with self.db.transaction():
                LocalRank.create(node_id = node_id, positivePayment = trustMod)
        except IntegrityError:
            LocalRank.update(positivePayment = LocalRank.positivePayment + trustMod, modified_date = str(datetime.datetime.now())).where(LocalRank.node_id == node_id).execute()

    ############################
    def increaseNegativePayment(self, node_id, trustMod):
        try:
            with self.db.transaction():
                LocalRank.create(node_id = node_id, negativePayment = trustMod)
        except IntegrityError:
            LocalRank.update(negativePayment = LocalRank.negativePayment + trustMod,  modified_date = str(datetime.datetime.now())).where(LocalRank.node_id == node_id).execute()

    ############################
    def increasePositiveResource(self, node_id, trustMod):
        try:
            with self.db.transaction():
                LocalRank.create(node_id = node_id, positiveResource = trustMod)
        except IntegrityError:
            LocalRank.update(positiveResource = LocalRank.positiveResource + trustMod, modified_date = str(datetime.datetime.now())).where(LocalRank.node_id == node_id).execute()

    ############################
    def increaseNegativeResource(self, node_id, trustMod):
        try:
            with self.db.transaction():
                LocalRank.create(node_id = node_id, negativeResource = trustMod)
        except IntegrityError:
            LocalRank.update(positiveResource = LocalRank.negativeResource + trustMod, modified_date = str(datetime.datetime.now())).where(LocalRank.node_id == node_id).execute()

    ############################
    def getLocalRank(self, node_id):
        return LocalRank.select().where(LocalRank.node_id == node_id).first()

    ############################
    def getGlobalRank(self, node_id):
        return GlobalRank.select().where(GlobalRank.node_id == node_id).first()

    ############################
    def insertOrUpdateGlobalRank(self, node_id, comp_trust, req_trust, compWeight, reqWeight):
        try:
            with self.db.transaction():
                GlobalRank.create(node_id = node_id, requestingTrustValue = req_trust, computingTrustValue = comp_trust, gossipWeightComputing = compWeight, gossipWeightRequesting = reqWeight)
        except IntegrityError:
            GlobalRank.update(requestingTrustValue = req_trust, computingTrustValue = comp_trust, gossipWeightComputing = compWeight, gossipWeightRequesting = reqWeight,  modified_date = str(datetime.datetime.now())).where(GlobalRank.node_id == node_id).execute()

    ############################
    def getAllLocalRank(self):
        return LocalRank.select()

    ############################
    def insertOrUpdateNeighbourLocRank(self, neighbourId, about_id, loc_rank):
        try:
            if neighbourId == about_id:
                logger.warning("Removing {} selftrust".format(about_id))
                return
            with self.db.transaction():
                NeighbourLocRank.create(node_id = neighbourId, aboutNodeId = about_id, requestingTrustValue = loc_rank[1], computingTrustValue = loc_rank[0])
        except IntegrityError:
            NeighbourLocRank.update(requestingTrustValue = loc_rank[1], computingTrustValue = loc_rank[0]).where(NeighbourLocRank.aboutNodeId == about_id and NeighbourLocRank.node_id == neighbourId).execute()

    ############################
    def getNeighbourLocRank(self, neighbourId, about_id):
        return NeighbourLocRank.select().where(NeighbourLocRank.node_id == neighbourId and NeighbourLocRank.aboutNodeId == about_id).first()

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
    ############################
    def __init__(self, client, database, posPar = POS_PAR, negPar = NEG_PAR, maxTrust = MAX_TRUST, minTrust = MIN_TRUST,
                 minOpNum = MIN_OP_NUM, unknownTrust = UNKNOWN_TRUST, max_steps = MAX_STEPS, epsilon = EPSILON,
                 loc_rankPushDelta = LOC_RANK_PUSH_DELTA):
        self.db = database
        self.client = client
        self.posPar = posPar
        self.negPar = negPar
        self.maxTrust = maxTrust
        self.minTrust = minTrust
        self.unknownTrust = unknownTrust
        self.minOpNum = minOpNum
        self.roundOracle = DiscreteTimeRoundOracle()

        self.k = 1
        self.epsilon = epsilon
        self.neighbours = []
        self.step = 0
        self.max_steps = max_steps
        self.workingVec = {}
        self.prevRank = {}
        self.globRank = {}
        self.receivedGossip = []
        self.finished = False
        self.finished_neighbours = set()
        self.global_finished = False
        self.reactor = None
        self.initLocRankPush = True
        self.prev_loc_rank = {}
        self.loc_rankPushDelta = loc_rankPushDelta

    ############################
    def run(self, reactor):
        self.reactor = reactor
        deferLater(self.reactor, self.roundOracle.sec_to_new_stage(), self.initStage)

    ############################
    def initStage(self):
        try:
            logger.debug("New gossip stage")
            self.__push_local_ranks()
            self.finished = False
            self.global_finished = False
            self.step = 0
            self.finished_neighbours = set()
            self.initWorkingVec()
        finally:
            deferLater(self.reactor, self.roundOracle.sec_to_round(), self.newRound)

    ############################
    def initWorkingVec(self):
        self.workingVec = {}
        self.prevRank = {}
        for loc_rank in self.db.getAllLocalRank():
            comp_trust = self.__count_trust(self.__get_comp_trust_pos(loc_rank), self.__get_comp_trust_neg(loc_rank))
            req_trust = self.__count_trust(self.__get_req_trust_pos(loc_rank), self.__get_req_trust_neg(loc_rank))
            self.workingVec[loc_rank.node_id] = [[comp_trust, 1.0], [req_trust, 1.0]]
            self.prevRank[loc_rank.node_id] = [ comp_trust, req_trust ]

    ############################
    def newRound(self):
        logger.debug("New gossip round")
        try:
            self.__set_k()
            self.step += 1
            gossip = self.__prepare_gossip()
            if len(self.neighbours) > 0:
                send_to = random.sample(self.neighbours, self.k)
                self.client.send_gossip(gossip, send_to)
            self.receivedGossip = [ gossip ]
        finally:
            deferLater(self.reactor, self.roundOracle.sec_to_end_round(), self.endRound)

    ############################
    def endRound(self):
        logger.debug("End gossip round")
        try:
            self.receivedGossip = self.client.collect_gossip() + self.receivedGossip
            self.__make_prev_rank()
            self.workingVec = {}
            self.__add_gossip()
            self.__check_finished()
        finally:
            deferLater(self.reactor, self.roundOracle.sec_to_break(), self.makeBreak)

    ############################
    def makeBreak(self):
        logger.debug("Gossip round finished")
        try:
            self.__check_global_finished()
        except Exception:
            deferLater(self.reactor, self.roundOracle.sec_to_round(), self.newRound)
            raise

        if self.global_finished:
            try:
                self.client.collect_gossip()
                self.client.collect_stopped_peers()
                self.__save_working_vec()
            finally:
                deferLater(self.reactor, self.roundOracle.sec_to_new_stage(), self.initStage)
        else:
            deferLater(self.reactor, self.roundOracle.sec_to_round(), self.newRound)

    ############################
    def increase_trust(self, node_id, stat, mod):
        if stat == RankingStats.computed:
            self.db.increasePositiveComputing(node_id, mod)
        elif stat == RankingStats.requested:
            self.db.increasePositiveRequested(node_id, mod)
        elif stat == RankingStats.payment:
            self.db.increasePositivePayment(node_id, mod)
        elif stat == RankingStats.resource:
            self.db.increasePositiveResource(node_id, mod)
        else:
            logger.error("Wrong stat type {}".format(stat))

   ############################
    def decrease_trust(self, node_id, stat, mod):
        if stat == RankingStats.computed:
            self.db.increaseNegativeComputing(node_id, mod)
        elif stat == RankingStats.wrongComputed:
            self.db.increaseWrongComputed(node_id, mod)
        elif stat == RankingStats.requested:
            self.db.increaseNegativeRequested(node_id, mod)
        elif stat == RankingStats.payment:
            self.db.increaseNegativePayment(node_id, mod)
        elif stat == RankingStats.resource:
            self.db.increaseNegativeResource(node_id, mod)
        else:
            logger.error("Wrong stat type {}".format(stat))

    ############################
    def getLocComputingTrust(self, node_id):
        localRank = self.db.getLocalRank(node_id)
        #Known node
        if localRank is not None:
            return self.__count_trust(self.__get_comp_trust_pos(localRank), self.__get_comp_trust_neg(localRank))
        return None

    ############################
    def get_computing_trust(self, node_id):
        localRank = self.getLocComputingTrust(node_id)
        if localRank is not None:
            logger.debug("Using local rank {}".format(localRank))
            return localRank
        rank, weightSum = self.__count_neighbours_rank(node_id, computing = True)
        globalRank = self.db.getGlobalRank(node_id)
        if globalRank is not None:
            if weightSum + globalRank.gossipWeightComputing != 0:
                logger.debug("Using gossipRank + neighboursRank")
                return (rank + globalRank.computingTrustValue) / (weightSum + globalRank.gossipWeightComputing)
        elif weightSum != 0:
            logger.debug("Using neighboursRank")
            return rank / float(weightSum)
        return self.unknownTrust

    ############################
    def getLocRequestingTrust(self, node_id):
        localRank = self.db.getLocalRank(node_id)
        #Known node
        if localRank is not None:
            return self.__count_trust(self.__get_req_trust_pos(localRank), self.__get_req_trust_neg(localRank))
        return None

    ############################
    def get_requesting_trust(self, node_id):
        localRank = self.getLocRequestingTrust(node_id)
        if localRank is not None:
            logger.debug("Using local rank {}".format(localRank))
            return localRank
        rank, weightSum = self.__count_neighbours_rank(node_id, computing = False)
        globalRank = self.db.getGlobalRank(node_id)
        if globalRank is not None:
            if globalRank.gossipWeightRequesting != 0:
                logger.debug("Using gossipRank + neighboursRank")
                return  (rank + globalRank.requestingTrustValue) / float(weightSum + globalRank.gossipWeightRequesting)
        elif weightSum != 0:
            logger.debug("Using neighboursRank")
            return rank / float(weightSum)

        return self.unknownTrust

    ############################
    def getComputingNeighbourLocTrust(self, neighbour, about):
        rank = self.db.getNeighbourLocRank(neighbour, about)
        if rank is not None:
            return rank.computingTrustValue
        return self.unknownTrust

    ############################
    def getRequestingNeighbourLocTrust(self, neighbour, about):
        rank = self.db.getNeighbourLocRank(neighbour, about)
        if rank is not None:
            return rank.requestingTrustValue
        return self.unknownTrust


    ############################
    def neighbourWeightBase(self):
        return 2

    ############################
    def neighbourWeightPower(self, node_id):
        return 2

    ############################
    def countNeighbourWeight(self, node_id, computing = True):
        if computing:
            locTrust = self.getLocComputingTrust(node_id)
        else:
            locTrust = self.getLocRequestingTrust(node_id)
        if locTrust is None:
            locTrust = self.unknownTrust
        return self.neighbourWeightBase() ** (self.neighbourWeightPower(node_id) * locTrust)

    def sync_network(self):
        neighboursLocRanks = self.client.collect_neighbours_loc_ranks()
        for [ neighbourId, about_id, loc_rank ] in neighboursLocRanks:
            self.db.insertOrUpdateNeighbourLocRank(neighbourId,
                                                   about_id, loc_rank)

    ############################
    def __push_local_ranks(self):
        for loc_rank in self.db.getAllLocalRank():
            if loc_rank.node_id in self.prev_loc_rank:
                prevTrust = self.prev_loc_rank[ loc_rank.node_id ]

            comp_trust = self.__count_trust(self.__get_comp_trust_pos(loc_rank), self.__get_comp_trust_neg(loc_rank))
            req_trust = self.__count_trust(self.__get_req_trust_pos(loc_rank), self.__get_req_trust_neg(loc_rank))
            trust = [ comp_trust, req_trust ]
            if loc_rank.node_id in self.prev_loc_rank:
                prevTrust = self.prev_loc_rank[ loc_rank.node_id ]
            else:
                prevTrust = [float("inf")] * 2
            if max(map(abs, map(operator.sub, prevTrust, trust))) > self.loc_rankPushDelta:
                self.client.push_local_rank(loc_rank.node_id, trust)
                self.prev_loc_rank[loc_rank.node_id] = trust



    ############################
    def __check_finished(self):
        if self.global_finished:
            return
        if not self.finished:
            if self.step >= self.max_steps:
                self.finished = True
                self.__send_finished()
            else:
                val = self.__compare_working_vec_and_prev_rank()
                if val <= len(self.workingVec) * self.epsilon * 2:
                    self.finished = True
                    self.__send_finished()


    ############################
    def __check_global_finished(self):
        self.__mark_finished(self.client.collect_stopped_peers())
        if self.finished:
            self.global_finished = True
            for n in self.neighbours:
                if n not in self.finished_neighbours:
                    self.global_finished = False
                    break

    ############################
    def __compare_working_vec_and_prev_rank(self):
        sum = 0.0
        for node_id, val in self.workingVec.iteritems():
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



    ############################
    def __count_trust(self, pos, neg):
        val = pos * self.posPar - neg * self.negPar
        val /= max(pos + neg, self.minOpNum)
        val = min(self.maxTrust, max(self.minTrust, val))
        return val

    ############################
    def __set_k(self):
        degrees = self.__get_neighbours_degree()
        sum_degrees = sum(degrees.itervalues())
        degree = len(degrees)
        if degree == 0:
            self.k = 0
        else:
            avg =  float(sum_degrees) / float(degree)
            self.k = max(int (round(float(degree) / avg)), 1)

    ############################
    def __get_neighbours_degree(self):
        degrees = self.client.get_neighbours_degree()
        self.neighbours = degrees.keys()
        return degrees

    ############################
    def __make_prev_rank(self):
        for node_id, val in self.workingVec.iteritems():
            try:
                computing, requesting = val
            except (TypeError, ValueError):
                logger.warning("Wrong trust vector element {}".format(val))
                break
            comp_trust = self.__working_vec_to_trust(computing)
            req_trust = self.__working_vec_to_trust(requesting)
            self.prevRank[node_id] = [comp_trust, req_trust]

    ############################
    def __save_working_vec(self):
        for node_id, val in self.workingVec.iteritems():
            try:
                computing, requesting = val
            except (TypeError, ValueError):
                logger.warning("Wrong trust vector element {}".format(val))
                break
            comp_trust = self.__working_vec_to_trust(computing)
            req_trust = self.__working_vec_to_trust(requesting)
            self.db.insertOrUpdateGlobalRank(node_id, comp_trust, req_trust,  computing[1], requesting[1])

    ############################
    def __working_vec_to_trust(self, val):
        if val == None:
            return 0.0
        try:
            a, b = val
        except Exception, err:
            logger.warning("Wrong trust vector element {}".format(str(err)))
            return None
        if a == 0.0 or b == 0.0:
            return 0.0
        else:
            return min(max(float(a) / float(b), self.minTrust), self.maxTrust)

    ############################
    def __prepare_gossip(self):
        gossip_vec = []
        for node_id, val in self.workingVec.iteritems():
            comp_trust = map(self.__scale_gossip, val[0])
            req_trust = map(self.__scale_gossip, val[1])
            gossip_vec.append([node_id, [comp_trust, req_trust]])
        return gossip_vec

    ############################
    def __scale_gossip(self, val):
        return val / float(self.k + 1)

    ############################
    def __add_gossip(self):
        for gossipGroup in self.receivedGossip:
            for gossip in gossipGroup:
                try:
                    node_id, [comp, req] = gossip
                    if node_id in self.workingVec:
                        [prev_comp, prev_req] = self.workingVec[node_id]
                        self.workingVec[node_id] = [self.__sum_gossip(comp, prev_comp), self.__sum_gossip(req, prev_req)]
                    else:
                        self.workingVec[node_id] = [comp, req]
                except Exception, err:
                    logger.error("Wrong gossip {}, {}".format(gossip, str(err)))

        self.receivedGossip = []

    ############################
    def __sum_gossip(self, a, b):
        return map(sum, izip(a, b))

    ############################
    def __send_finished(self):
        self.client.send_stop_gossip()

    ############################
    def __mark_finished(self, finished):
        self.finished_neighbours |= finished

    ############################
    def __count_neighbours_rank(self, node_id, computing):
        sum_weight = 0.0
        sum_trust = 0.0
        for n in self.neighbours:
            if n != node_id:
                if computing:
                    trust = self.getComputingNeighbourLocTrust(n, node_id)
                else:
                    trust = self.getRequestingNeighbourLocTrust(n, node_id)
                weight = self.countNeighbourWeight(n, not computing)
                sum_trust += (weight - 1) * trust
                sum_weight += weight
        return sum_trust, sum_weight

    ############################
    def __get_comp_trust_pos(self, rank):
        return rank.positiveComputed

    ############################
    def __get_comp_trust_neg(self, rank):
        return rank.negativeComputed + rank.wrongComputed

    ############################
    def __get_req_trust_pos(self, rank):
        return rank.positivePayment

    ############################
    def __get_req_trust_neg(self, rank):
        return rank.negativeRequested + rank.negativePayment

####################################################################################

from golem.core.variables import BREAK_TIME, ROUND_TIME, END_ROUND_TIME, STAGE_TIME

class DiscreteTimeRoundOracle:
    def __init__(self, break_time = BREAK_TIME, round_time = ROUND_TIME, end_round_time = END_ROUND_TIME, stage_time = STAGE_TIME):
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
        if self.round_time + self.end_round_time -tm >= 0:
            return self.round_time + self.end_round_time - tm
        else:
            return self.__sum_time() + self.round_time + self.end_round_time - tm

    def sec_to_new_stage(self):
        return self.stage_time - time.time() % self.stage_time
