import logging
import time
import random

from twisted.internet.task import deferLater
from itertools import izip

logger = logging.getLogger(__name__)
from peewee import IntegrityError
from golem.Model import LocalRank, GlobalRank

class RankingDatabase:
    def __init__(self, database):
        self.db = database.db

    ############################
    def increaseComputingTrust(self, nodeId, trustMod):
        try:
            with self.db.transaction():
                LocalRank.create(nodeId=nodeId, positiveComputed=trustMod)
        except IntegrityError:
            LocalRank.update(positiveComputed = LocalRank.positiveComputed + trustMod).where(nodeId == nodeId).execute()

    ############################
    def decreaseComputingTrust(self, nodeId, trustMod):
        try:
            with self.db.transaction():
                LocalRank.create(nodeId = nodeId, negativeComputed = trustMod)
        except IntegrityError:
            LocalRank.update(negativeComputed = LocalRank.negativeComputed + trustMod).where(nodeId == nodeId).execute()

    ############################
    def increaseRequesterTrust(self, nodeId, trustMod):
        try:
            with self.db.transaction():
                LocalRank.create(nodeId = nodeId, positiveRequested = trustMod)
        except IntegrityError:
            LocalRank.update(positiveRequested = LocalRank.positiveRequested + trustMod).where(nodeId == nodeId).execute()

    ############################
    def decreaseRequesterTrust(self, nodeId, trustMod):
        try:
            with self.db.transaction():
                LocalRank.create(nodeId = nodeId, negativeRequested = trustMod)
        except IntegrityError:
            LocalRank.update(negativeRequested = LocalRank.negativeRequested + trustMod).where(nodeId == nodeId).execute()

    ############################
    def getLocalRank(self, nodeId ):
        return LocalRank.select().where(LocalRank.nodeId == nodeId).first()

    ############################
    def getGlobalRank(self, nodeId):
        return GlobalRank.select().where(GlobalRank.nodeId == nodeId ).first()

    def insertOrUpdateGlobalRank( self, nodeId, compTrust, reqTrust ):
        try:
            with self.db.transaction():
                GlobalRank.create( nodeId = nodeId, requestingTrustValue = reqTrust, computingTrustValue = compTrust )
        except IntegrityError:
            GlobalRank.update(requestingTrustValue = reqTrust, computingTrustValue = compTrust).where( nodeId == nodeId ).execute()

    def getAllLocalRank(self):
        return LocalRank.select()

POS_PAR = 1.0
NEG_PAR = 2.0
MAX_TRUST = 1.0
MIN_TRUST = -1.0
UNKNOWN_TRUST = 0.0
MIN_OP_NUM = 50
MAX_STEPS = 10
EPSILON = 0.01

class Ranking:
    ############################
    def __init__(self, client, database, posPar = POS_PAR, negPar = NEG_PAR, maxTrust = MAX_TRUST, minTrust = MIN_TRUST, minOpNum = MIN_OP_NUM, unknownTrust = UNKNOWN_TRUST, maxSteps = MAX_STEPS, epsilon = EPSILON):
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

    ############################
    def run(self, reactor):
        self.reactor = reactor
        deferLater(self.reactor, self.roundOracle.secToNewStage(), self.initStage)

    ############################
    def initStage(self):
        logger.debug("New gossip stage")
        self.finished = False
        self.globalFinished = False
        self.step = 0
        self.finishedNeighbours = set()
        self.initWorkingVec()
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
    def getComputingTrust( self, nodeId ):
        localRank = self.db.getLocalRank( nodeId )
        #Known node
        if localRank is not None:
            return self.__countTrust( localRank.positiveComputed, localRank.negativeComputed )
        globalRank = self.db.getGlobalRank(nodeId)
        if globalRank is not None:
            return globalRank.computingTrustValue
        return self.unknownTrust

    ############################
    def getRequestingTrust(self, nodeId):
        localRank = self.db.getLocalRank( nodeId )
        if localRank is not None:
            return self.__countTrust( localRank.positiveRequested, localRank.negativeRequested )
        globalRank = self.db.getGlobalRank( nodeId )
        if globalRank is not None:
            return globalRank.requestingTrustValue
        return self.unknownTrust

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
            self.db.insertOrUpdateGlobalRank( nodeId, compTrust, reqTrust )

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

####################################################################################

BREAK_TIME = 3
END_ROUND_TIME = 3
ROUND_TIME = 6
STAGE_TIME = 300

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
            return self.__sumTime + self.roundTime + self.endRoundTime - tm

    def secToNewStage(self):
        return self.stageTime - time.time() % self.stageTime
