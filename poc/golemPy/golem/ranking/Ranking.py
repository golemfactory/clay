import logging

logger = logging.getLogger(__name__)
from golem.Model import LocalRank, IntegrityError

POS_PAR = 1.0
NEG_PAR = 2.0
MAX_TRUST = 1.0
MIN_TRUST = -1.0
MIN_OP_NUM = 50

class Ranking:
    ############################
    def __init__(self, database, posPar = POS_PAR, negPar = NEG_PAR, maxTrust = MAX_TRUST, minTrust = MIN_TRUST, minOpNum = MIN_OP_NUM):
        self.db = database.db
        self.posPar = posPar
        self.negPar = negPar
        self.maxTrust = maxTrust
        self.minTrust = minTrust
        self.minOpNum = minOpNum

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
    def getComputingTrust( self, nodeId ):
        try:
            localRank = LocalRank.get(LocalRank.nodeId == nodeId )
            return self.__countTrust( localRank.positiveComputed, localRank.negativeComputed )
        except Exception, err:
            logger.debug( "LocalRank exception {}".format(str(err)))
            return 0.0

    ############################
    def getRequestingTrust(self, nodeId):
        try:
            localRank = LocalRank.get(LocalRank.nodeId == nodeId )
            return self.__countTrust( localRank.positiveRequested, localRank.negativeRequested )
        except Exception, err:
            logger.debug( "LocalRank exception {}".format(str(err)))
            return 0.0

    ############################
    def __countTrust(self, pos, neg):
        val = pos * self.posPar - neg * self.negPar
        val /= max(pos + neg, self.minOpNum)
        val = min(self.maxTrust, max(self.minTrust, val))
        return val