import logging
import time
import random
import operator

from twisted.internet.task import deferLater
from itertools import izip

logger = logging.getLogger(__name__)
from peewee import IntegrityError
from golem.Model import LocalRank, GlobalRank, NeighbourLocRank

class RankingDatabase:
    def __init__(self, database):
        self.db = database.db

    ############################
    def increaseComputingTrust(self, nodeId, trustMod):
        try:
            with self.db.transaction():
                LocalRank.create(nodeId=nodeId, positiveComputed=trustMod)
        except IntegrityError:
            LocalRank.update(positiveComputed = LocalRank.positiveComputed + trustMod).where(LocalRank.nodeId == nodeId).execute()

    ############################
    def decreaseComputingTrust(self, nodeId, trustMod):
        try:
            with self.db.transaction():
                LocalRank.create(nodeId = nodeId, negativeComputed = trustMod)
        except IntegrityError:
            LocalRank.update(negativeComputed = LocalRank.negativeComputed + trustMod).where(LocalRank.nodeId == nodeId).execute()

    ############################
    def increaseRequesterTrust(self, nodeId, trustMod):
        try:
            with self.db.transaction():
                LocalRank.create(nodeId = nodeId, positiveRequested = trustMod)
        except IntegrityError:
            LocalRank.update(positiveRequested = LocalRank.positiveRequested + trustMod).where(LocalRank.nodeId == nodeId).execute()

    ############################
    def decreaseRequesterTrust(self, nodeId, trustMod):
        try:
            with self.db.transaction():
                LocalRank.create(nodeId = nodeId, negativeRequested = trustMod)
        except IntegrityError:
            LocalRank.update(negativeRequested = LocalRank.negativeRequested + trustMod).where(LocalRank.nodeId == nodeId).execute()

    ############################
    def getLocalRank(self, nodeId ):
        return LocalRank.select().where(LocalRank.nodeId == nodeId).first()

    ############################
    def getGlobalRank(self, nodeId):
        return GlobalRank.select().where(GlobalRank.nodeId == nodeId ).first()

    ############################
    def insertOrUpdateGlobalRank( self, nodeId, compTrust, reqTrust, compWeight, reqWeight ):
        try:
            with self.db.transaction():
                GlobalRank.create( nodeId = nodeId, requestingTrustValue = reqTrust, computingTrustValue = compTrust, gossipWeightComputing = compWeight, gossipWeightRequesting = reqWeight )
        except IntegrityError:
            GlobalRank.update(requestingTrustValue = reqTrust, computingTrustValue = compTrust, gossipWeightComputing = compWeight, gossipWeightRequesting = reqWeight).where( GlobalRank.nodeId == nodeId ).execute()

    ############################
    def getAllLocalRank(self):
        return LocalRank.select()

    ############################
    def insertOrUpdateNeighbourLocRank( self, neighbourId, aboutId, locRank ):
        try:
            if neighbourId == aboutId:
                logger.warning("Removing {} selftrust".format( aboutId ) )
                return
            with self.db.transaction():
                NeighbourLocRank.create( nodeId = neighbourId, aboutNodeId = aboutId, requestingTrustValue = locRank[1], computingTrustValue = locRank[0] )
        except IntegrityError:
            NeighbourLocRank.update( requestingTrustValue = locRank[1], computingTrustValue = locRank[0]).where( NeighbourLocRank.aboutNodeId == aboutId and NeighbourLocRank.nodeId == neighbourId ).execute()

    ############################
    def getNeighbourLocRank( self, neighbourId, aboutId ):
        return NeighbourLocRank.select().where(NeighbourLocRank.nodeId == neighbourId and NeighbourLocRank.aboutNodeId == aboutId).first()

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
                 locRankPushDelta = LOC_RANK_PUSH_DELTA ):
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
            self.__pushLocalRanks()
            self.finished = False
            self.globalFinished = False
            self.step = 0
            self.finishedNeighbours = set()
            self.initWorkingVec()
        finally:
            deferLater( self.reactor, self.roundOracle.secToRound(), self.newRound)

    ############################
    def initWorkingVec( self ):
        self.workingVec = {}
        self.prevRank = {}
        for locRank in self.db.getAllLocalRank():
            compTrust = self.__countTrust( locRank.positiveComputed, locRank.negativeComputed )
            reqTrust = self.__countTrust( locRank.positiveRequested, locRank.negativeRequested )
            self.workingVec[locRank.nodeId] = [[compTrust, 1.0], [reqTrust, 1.0]]
            self.prevRank[locRank.nodeId] = [ compTrust, reqTrust ]

    ############################
    def newRound(self):
        logger.debug("New gossip round")
        try:
            self.__setK()
            self.step += 1
            gossip = self.__prepareGossip()
            if len( self.neighbours) > 0:
                sendTo = random.sample(self.neighbours, self.k)
                self.client.sendGossip(gossip, sendTo)
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
                deferLater( self.reactor, self.roundOracle.secToNewStage(), self.initStage)
        else:
            deferLater(self.reactor, self.roundOracle.secToRound(), self.newRound)

    ############################
    def increaseComputingTrust(self, nodeId, trustMod):
        self.db.increaseComputingTrust( nodeId, trustMod )

    ############################
    def decreaseComputingTrust(self, nodeId, trustMod):
        self.db.decreaseComputingTrust( nodeId, trustMod )

    ############################
    def increaseRequesterTrust(self, nodeId, trustMod):
        self.db.increaseRequesterTrust( nodeId, trustMod )

    ############################
    def decreaseRequesterTrust(self, nodeId, trustMod):
        self.db.decreaseComputingTrust( nodeId, trustMod )

    ############################
    def getLocComputingTrust(self, nodeId ):
        localRank = self.db.getLocalRank( nodeId )
        #Known node
        if localRank is not None:
            return self.__countTrust( localRank.positiveComputed, localRank.negativeComputed )
        return None

    ############################
    def getComputingTrust( self, nodeId ):
        localRank = self.getLocComputingTrust( nodeId )
        if localRank is not None:
            logger.debug("Using local rank {}".format( localRank ))
            return localRank
        rank, weightSum = self.__countNeighboursRank(nodeId, computing = True)
        globalRank = self.db.getGlobalRank(nodeId)
        if globalRank is not None:
            if weightSum + globalRank.gossipWeightComputing != 0:
                logger.debug("Using gossipRank + neighboursRank")
                return (rank + globalRank.computingTrustValue ) / (weightSum + globalRank.gossipWeightComputing)
        elif weightSum != 0:
            logger.debug("Using neighboursRank")
            return rank / float(weightSum)
        return self.unknownTrust

    ############################
    def getLocRequestingTrust(self, nodeId ):
        localRank = self.db.getLocalRank( nodeId )
        #Known node
        if localRank is not None:
            return self.__countTrust( localRank.positiveRequested, localRank.negativeRequested )
        return None

    ############################
    def getRequestingTrust(self, nodeId):
        localRank = self.getLocRequestingTrust( nodeId )
        if localRank is not None:
            logger.debug("Using local rank {}".format( localRank ))
            return localRank
        rank, weightSum = self.__countNeighboursRank(nodeId, computing = False)
        globalRank = self.db.getGlobalRank( nodeId )
        if globalRank is not None:
            if globalRank.gossipWeightRequesting != 0:
                logger.debug("Using gossipRank + neighboursRank")
                return  (rank + globalRank.requestingTrustValue ) / float(weightSum + globalRank.gossipWeightRequesting)
        elif weightSum != 0:
            logger.debug("Using neighboursRank")
            return rank / float(weightSum)

        return self.unknownTrust

    ############################
    def getComputingNeighbourLocTrust( self, neighbour, about ):
        rank = self.db.getNeighbourLocRank( neighbour, about )
        if rank is not None:
            return rank.computingTrustValue
        return self.unknownTrust

    ############################
    def getRequestingNeighbourLocTrust( self, neighbour, about ):
        rank = self.db.getNeighbourLocRank( neighbour, about )
        if rank is not None:
            return rank.requestingTrustValue
        return self.unknownTrust


    ############################
    def neighbourWeightBase( self):
        return 2

    ############################
    def neighbourWeightPower( self, nodeId ):
        return 2

    ############################
    def countNeighbourWeight(self, nodeId, computing = True ):
        if computing:
            locTrust = self.getLocComputingTrust( nodeId )
        else:
            locTrust = self.getLocRequestingTrust( nodeId )
        if locTrust is None:
            locTrust = self.unknownTrust
        return self.neighbourWeightBase() ** ( self.neighbourWeightPower( nodeId ) * locTrust )

    def syncNetwork(self):
        neighboursLocRanks = self.client.collectNeighboursLocRanks()
        for [ neighbourId, aboutId, locRank ] in neighboursLocRanks:
            self.db.insertOrUpdateNeighbourLocRank( neighbourId, aboutId, locRank )

    ############################
    def __pushLocalRanks( self ):
        for locRank in self.db.getAllLocalRank():
            if locRank.nodeId in self.prevLocRank:
                prevTrust = self.prevLocRank[ locRank.nodeId ]

            compTrust = self.__countTrust( locRank.positiveComputed, locRank.negativeComputed )
            reqTrust = self.__countTrust( locRank.positiveRequested, locRank.negativeRequested )
            trust = [ compTrust, reqTrust ]
            if locRank.nodeId in self.prevLocRank:
                prevTrust = self.prevLocRank[ locRank.nodeId ]
            else:
                prevTrust = [float("inf")] * 2
            if max( map( abs, map( operator.sub, prevTrust, trust) ) ) > self.locRankPushDelta:
                self.client.pushLocalRank( locRank.nodeId, trust )
                self.prevLocRank[locRank.nodeId] = trust



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
                if val <= len( self.workingVec ) * self.epsilon * 2:
                    self.finished = True
                    self.__sendFinished()


    ############################
    def __checkGlobalFinished(self):
        self.__markFinished( self.client.collectStoppedPeers() )
        if self.finished:
            self.globalFinished = True
            for n in self.neighbours:
                if n not in self.finishedNeighbours:
                    self.globalFinished = False
                    break

    ############################
    def __compareWorkingVecAndPrevRank(self ):
        sum = 0.0
        for nodeId, val in self.workingVec.iteritems():
            try:
                computing, requesting = val
            except (TypeError, ValueError):
                logger.warning("Wrong trust vector element {}".format( val ) )
                break
            compTrust = self.__workingVecToTrust( computing )
            reqTrust = self.__workingVecToTrust( requesting )
            if nodeId in self.prevRank:
                compTrustOld = self.prevRank[nodeId][0]
                reqTrustOld = self.prevRank[nodeId][1]
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
    def __setK( self ):
        degrees = self.__getNeighboursDegree()
        sumDegrees = sum( degrees.itervalues() )
        degree = len( degrees )
        if degree == 0:
            self.k = 0
        else:
            avg =  float( sumDegrees ) / float( degree )
            self.k = max( int ( round( float( degree ) / avg ) ), 1)

    ############################
    def __getNeighboursDegree(self):
        degrees = self.client.getNeighboursDegree()
        self.neighbours = degrees.keys()
        return degrees

    ############################
    def __makePrevRank( self ):
        for nodeId, val in self.workingVec.iteritems():
            try:
                computing, requesting = val
            except (TypeError, ValueError):
                logger.warning("Wrong trust vector element {}".format( val ) )
                break
            compTrust = self.__workingVecToTrust( computing )
            reqTrust = self.__workingVecToTrust( requesting )
            self.prevRank[nodeId] = [compTrust, reqTrust]

    ############################
    def __saveWorkingVec( self ):
        for nodeId, val in self.workingVec.iteritems():
            try:
                computing, requesting = val
            except (TypeError, ValueError):
                logger.warning("Wrong trust vector element {}".format( val ) )
                break
            compTrust = self.__workingVecToTrust( computing )
            reqTrust = self.__workingVecToTrust( requesting )
            self.db.insertOrUpdateGlobalRank( nodeId, compTrust, reqTrust,  computing[1], requesting[1] )

    ############################
    def __workingVecToTrust(self, val):
        if val == None:
            return 0.0
        try:
            a, b = val
        except Exception, err:
            logger.warning("Wrong trust vector element {}".format( str( err ) ) )
            return None
        if a == 0.0 or b == 0.0:
            return 0.0
        else:
            return min( max( float( a ) / float( b ), self.minTrust), self.maxTrust)

    ############################
    def __prepareGossip( self ):
        gossipVec = []
        for nodeId, val in self.workingVec.iteritems():
            compTrust = map(self.__scaleGossip, val[0])
            reqTrust = map( self.__scaleGossip, val[1])
            gossipVec.append([nodeId, [compTrust, reqTrust]])
        return gossipVec

    ############################
    def __scaleGossip( self, val ):
        return val / float(self.k + 1)

    ############################
    def __addGossip(self):
        for gossipGroup in self.receivedGossip:
            for gossip in gossipGroup:
                try:
                    nodeId, [comp, req] = gossip
                    if nodeId in self.workingVec:
                        [prevComp, prevReq] = self.workingVec[nodeId]
                        self.workingVec[nodeId] = [self.__sumGossip(comp, prevComp), self.__sumGossip(req, prevReq)]
                    else:
                        self.workingVec[nodeId] = [comp, req]
                except Exception, err:
                    logger.error("Wrong gossip {}, {}".format(gossip, str(err)))

        self.receivedGossip = []

    ############################
    def __sumGossip(self, a, b):
        return map(sum, izip(a, b))

    ############################
    def __sendFinished(self):
        self.client.sendStopGossip()

    ############################
    def __markFinished(self, finished):
        self.finishedNeighbours |= finished

    ############################
    def __countNeighboursRank( self, nodeId, computing ):
        sumWeight = 0.0
        sumTrust = 0.0
        for n in self.neighbours:
            if n != nodeId:
                if computing:
                    trust = self.getComputingNeighbourLocTrust( n, nodeId )
                else:
                    trust = self.getRequestingNeighbourLocTrust( n, nodeId )
                weight = self.countNeighbourWeight( n, not computing )
                sumTrust += (weight - 1) * trust
                sumWeight += weight
        return sumTrust, sumWeight


####################################################################################

from golem.core.variables import BREAK_TIME, ROUND_TIME, END_ROUND_TIME, STAGE_TIME

class DiscreteTimeRoundOracle:
    def __init__(self, breakTime = BREAK_TIME, roundTime = ROUND_TIME, endRoundTime = END_ROUND_TIME, stageTime = STAGE_TIME ):
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
