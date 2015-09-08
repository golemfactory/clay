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
    def insertOrUpdateGlobalRank(self, node_id, compTrust, reqTrust, compWeight, reqWeight):
        try:
            with self.db.transaction():
                GlobalRank.create(node_id = node_id, requestingTrustValue = reqTrust, computingTrustValue = compTrust, gossipWeightComputing = compWeight, gossipWeightRequesting = reqWeight)
        except IntegrityError:
            GlobalRank.update(requestingTrustValue = reqTrust, computingTrustValue = compTrust, gossipWeightComputing = compWeight, gossipWeightRequesting = reqWeight,  modified_date = str(datetime.datetime.now())).where(GlobalRank.node_id == node_id).execute()

    ############################
    def getAllLocalRank(self):
        return LocalRank.select()

    ############################
    def insertOrUpdateNeighbourLocRank(self, neighbourId, about_id, locRank):
        try:
            if neighbourId == about_id:
                logger.warning("Removing {} selftrust".format(about_id))
                return
            with self.db.transaction():
                NeighbourLocRank.create(node_id = neighbourId, aboutNodeId = about_id, requestingTrustValue = locRank[1], computingTrustValue = locRank[0])
        except IntegrityError:
            NeighbourLocRank.update(requestingTrustValue = locRank[1], computingTrustValue = locRank[0]).where(NeighbourLocRank.aboutNodeId == about_id and NeighbourLocRank.node_id == neighbourId).execute()

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
                 minOpNum = MIN_OP_NUM, unknownTrust = UNKNOWN_TRUST, maxSteps = MAX_STEPS, epsilon = EPSILON,
                 locRankPushDelta = LOC_RANK_PUSH_DELTA):
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
        self.maxSteps = maxSteps
        self.workingVec = {}
        self.prevRank = {}
        self.globRank = {}
        self.receivedGossip = []
        self.finished = False
        self.finishedNeighbours = set()
        self.globalFinished = False
        self.reactor = None
        self.initLocRankPush = True
        self.prevLocRank = {}
        self.locRankPushDelta = locRankPushDelta

    ############################
    def run(self, reactor):
        self.reactor = reactor
        deferLater(self.reactor, self.roundOracle.secToNewStage(), self.initStage)

    ############################
    def initStage(self):
        try:
            logger.debug("New gossip stage")
            self.__push_local_ranks()
            self.finished = False
            self.globalFinished = False
            self.step = 0
            self.finishedNeighbours = set()
            self.initWorkingVec()
        finally:
            deferLater(self.reactor, self.roundOracle.secToRound(), self.newRound)

    ############################
    def initWorkingVec(self):
        self.workingVec = {}
        self.prevRank = {}
        for locRank in self.db.getAllLocalRank():
            compTrust = self.__countTrust(self.__getCompTrustPos(locRank), self.__getCompTrustNeg(locRank))
            reqTrust = self.__countTrust(self.__getReqTrustPos(locRank), self.__getReqTrustNeg(locRank))
            self.workingVec[locRank.node_id] = [[compTrust, 1.0], [reqTrust, 1.0]]
            self.prevRank[locRank.node_id] = [ compTrust, reqTrust ]

    ############################
    def newRound(self):
        logger.debug("New gossip round")
        try:
            self.__setK()
            self.step += 1
            gossip = self.__prepareGossip()
            if len(self.neighbours) > 0:
                send_to = random.sample(self.neighbours, self.k)
                self.client.send_gossip(gossip, send_to)
            self.receivedGossip = [ gossip ]
        finally:
            deferLater(self.reactor, self.roundOracle.secToEndRound(), self.endRound)

    ############################
    def endRound(self):
        logger.debug("End gossip round")
        try:
            self.receivedGossip = self.client.collectGossip() + self.receivedGossip
            self.__makePrevRank()
            self.workingVec = {}
            self.__addGossip()
            self.__checkFinished()
        finally:
            deferLater(self.reactor, self.roundOracle.secToBreak(), self.makeBreak)

    ############################
    def makeBreak(self):
        logger.debug("Gossip round finished")
        try:
            self.__checkGlobalFinished()
        except Exception:
            deferLater(self.reactor, self.roundOracle.secToRound(), self.newRound)
            raise

        if self.globalFinished:
            try:
                self.client.collectGossip()
                self.client.collectStoppedPeers()
                self.__saveWorkingVec()
            finally:
                deferLater(self.reactor, self.roundOracle.secToNewStage(), self.initStage)
        else:
            deferLater(self.reactor, self.roundOracle.secToRound(), self.newRound)

    ############################
    def increaseTrust(self, node_id, stat, mod):
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
    def decreaseTrust(self, node_id, stat, mod):
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
            return self.__countTrust(self.__getCompTrustPos(localRank), self.__getCompTrustNeg(localRank))
        return None

    ############################
    def get_computing_trust(self, node_id):
        localRank = self.getLocComputingTrust(node_id)
        if localRank is not None:
            logger.debug("Using local rank {}".format(localRank))
            return localRank
        rank, weightSum = self.__countNeighboursRank(node_id, computing = True)
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
            return self.__countTrust(self.__getReqTrustPos(localRank), self.__getReqTrustNeg(localRank))
        return None

    ############################
    def getRequestingTrust(self, node_id):
        localRank = self.getLocRequestingTrust(node_id)
        if localRank is not None:
            logger.debug("Using local rank {}".format(localRank))
            return localRank
        rank, weightSum = self.__countNeighboursRank(node_id, computing = False)
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
        neighboursLocRanks = self.client.collectNeighboursLocRanks()
        for [ neighbourId, about_id, locRank ] in neighboursLocRanks:
            self.db.insertOrUpdateNeighbourLocRank(neighbourId,
                                                   about_id, locRank)

    ############################
    def __push_local_ranks(self):
        for locRank in self.db.getAllLocalRank():
            if locRank.node_id in self.prevLocRank:
                prevTrust = self.prevLocRank[ locRank.node_id ]

            compTrust = self.__countTrust(self.__getCompTrustPos(locRank), self.__getCompTrustNeg(locRank))
            reqTrust = self.__countTrust(self.__getReqTrustPos(locRank), self.__getReqTrustNeg(locRank))
            trust = [ compTrust, reqTrust ]
            if locRank.node_id in self.prevLocRank:
                prevTrust = self.prevLocRank[ locRank.node_id ]
            else:
                prevTrust = [float("inf")] * 2
            if max(map(abs, map(operator.sub, prevTrust, trust))) > self.locRankPushDelta:
                self.client.push_local_rank(locRank.node_id, trust)
                self.prevLocRank[locRank.node_id] = trust



    ############################
    def __checkFinished(self):
        if self.globalFinished:
            return
        if not self.finished:
            if self.step >= self.maxSteps:
                self.finished = True
                self.__sendFinished()
            else:
                val = self.__compareWorkingVecAndPrevRank()
                if val <= len(self.workingVec) * self.epsilon * 2:
                    self.finished = True
                    self.__sendFinished()


    ############################
    def __checkGlobalFinished(self):
        self.__markFinished(self.client.collectStoppedPeers())
        if self.finished:
            self.globalFinished = True
            for n in self.neighbours:
                if n not in self.finishedNeighbours:
                    self.globalFinished = False
                    break

    ############################
    def __compareWorkingVecAndPrevRank(self):
        sum = 0.0
        for node_id, val in self.workingVec.iteritems():
            try:
                computing, requesting = val
            except (TypeError, ValueError):
                logger.warning("Wrong trust vector element {}".format(val))
                break
            compTrust = self.__workingVecToTrust(computing)
            reqTrust = self.__workingVecToTrust(requesting)
            if node_id in self.prevRank:
                compTrustOld = self.prevRank[node_id][0]
                reqTrustOld = self.prevRank[node_id][1]
            else:
                compTrustOld, reqTrustOld = 0, 0
            sum += abs(compTrust - compTrustOld) + abs(reqTrust - reqTrustOld)
        return sum



    ############################
    def __countTrust(self, pos, neg):
        val = pos * self.posPar - neg * self.negPar
        val /= max(pos + neg, self.minOpNum)
        val = min(self.maxTrust, max(self.minTrust, val))
        return val

    ############################
    def __setK(self):
        degrees = self.__getNeighboursDegree()
        sumDegrees = sum(degrees.itervalues())
        degree = len(degrees)
        if degree == 0:
            self.k = 0
        else:
            avg =  float(sumDegrees) / float(degree)
            self.k = max(int (round(float(degree) / avg)), 1)

    ############################
    def __getNeighboursDegree(self):
        degrees = self.client.getNeighboursDegree()
        self.neighbours = degrees.keys()
        return degrees

    ############################
    def __makePrevRank(self):
        for node_id, val in self.workingVec.iteritems():
            try:
                computing, requesting = val
            except (TypeError, ValueError):
                logger.warning("Wrong trust vector element {}".format(val))
                break
            compTrust = self.__workingVecToTrust(computing)
            reqTrust = self.__workingVecToTrust(requesting)
            self.prevRank[node_id] = [compTrust, reqTrust]

    ############################
    def __saveWorkingVec(self):
        for node_id, val in self.workingVec.iteritems():
            try:
                computing, requesting = val
            except (TypeError, ValueError):
                logger.warning("Wrong trust vector element {}".format(val))
                break
            compTrust = self.__workingVecToTrust(computing)
            reqTrust = self.__workingVecToTrust(requesting)
            self.db.insertOrUpdateGlobalRank(node_id, compTrust, reqTrust,  computing[1], requesting[1])

    ############################
    def __workingVecToTrust(self, val):
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
    def __prepareGossip(self):
        gossipVec = []
        for node_id, val in self.workingVec.iteritems():
            compTrust = map(self.__scaleGossip, val[0])
            reqTrust = map(self.__scaleGossip, val[1])
            gossipVec.append([node_id, [compTrust, reqTrust]])
        return gossipVec

    ############################
    def __scaleGossip(self, val):
        return val / float(self.k + 1)

    ############################
    def __addGossip(self):
        for gossipGroup in self.receivedGossip:
            for gossip in gossipGroup:
                try:
                    node_id, [comp, req] = gossip
                    if node_id in self.workingVec:
                        [prevComp, prevReq] = self.workingVec[node_id]
                        self.workingVec[node_id] = [self.__sumGossip(comp, prevComp), self.__sumGossip(req, prevReq)]
                    else:
                        self.workingVec[node_id] = [comp, req]
                except Exception, err:
                    logger.error("Wrong gossip {}, {}".format(gossip, str(err)))

        self.receivedGossip = []

    ############################
    def __sumGossip(self, a, b):
        return map(sum, izip(a, b))

    ############################
    def __sendFinished(self):
        self.client.send_stop_gossip()

    ############################
    def __markFinished(self, finished):
        self.finishedNeighbours |= finished

    ############################
    def __countNeighboursRank(self, node_id, computing):
        sumWeight = 0.0
        sumTrust = 0.0
        for n in self.neighbours:
            if n != node_id:
                if computing:
                    trust = self.getComputingNeighbourLocTrust(n, node_id)
                else:
                    trust = self.getRequestingNeighbourLocTrust(n, node_id)
                weight = self.countNeighbourWeight(n, not computing)
                sumTrust += (weight - 1) * trust
                sumWeight += weight
        return sumTrust, sumWeight

    ############################
    def __getCompTrustPos(self, rank):
        return rank.positiveComputed

    ############################
    def __getCompTrustNeg(self, rank):
        return rank.negativeComputed + rank.wrongComputed

    ############################
    def __getReqTrustPos(self, rank):
        return rank.positivePayment

    ############################
    def __getReqTrustNeg(self, rank):
        return rank.negativeRequested + rank.negativePayment

####################################################################################

from golem.core.variables import BREAK_TIME, ROUND_TIME, END_ROUND_TIME, STAGE_TIME

class DiscreteTimeRoundOracle:
    def __init__(self, breakTime = BREAK_TIME, roundTime = ROUND_TIME, endRoundTime = END_ROUND_TIME, stageTime = STAGE_TIME):
        self.breakTime = breakTime
        self.roundTime = roundTime
        self.endRoundTime = endRoundTime
        self.stageTime = stageTime

    def __sumTime(self):
        return self.roundTime + self.breakTime + self.endRoundTime

    def __timeMod(self):
        return time.time() % self.__sumTime()

    def isBreak(self):
        return self.roundTime + self.endRoundTime < self.__timeMod()

    def isRound(self):
        return self.__timeMod() <= self.roundTime

    def isEndRound(self):
        return self.roundTime < self.__timeMod() <= self.roundTime + self.endRoundTime

    def secToEndRound(self):
        tm = self.__timeMod()
        if self.roundTime - tm >= 0:
            return self.roundTime - tm
        else:
            return self.__sumTime() + self.roundTime - tm

    def secToRound(self):
        return self.__sumTime() - self.__timeMod()

    def secToBreak(self):
        tm = self.__timeMod()
        if self.roundTime + self.endRoundTime -tm >= 0:
            return self.roundTime + self.endRoundTime - tm
        else:
            return self.__sumTime() + self.roundTime + self.endRoundTime - tm

    def secToNewStage(self):
        return self.stageTime - time.time() % self.stageTime
