from numpy import zeros, hstack, vstack, matrix
import math
from random import randint, sample

class GossipTrustTest:
    def __init__(self, epsilon = 0.1, delta = 0.1, gossipScoreMaxSteps = 10000, aggregationMaxSteps = 4):
        self.localRanking = None
        self.localRankingMapping = {}
        self.lastGlobalRanking = None
        self.globalRanking = None
        self.epsilon = epsilon
        self.delta = delta
        self.gossipScoreSteps = 0
        self.gossipScoreMaxSteps = gossipScoreMaxSteps
        self.aggregationSteps = 0
        self.aggregationMaxSteps = aggregationMaxSteps
        self.globalReputationCycles = 0
        #self.outerSend = outerSender
        self.weightedScores = None
        self.consensusFactors = None
        self.collectedPairs = None
        self.previousScore = None
        self.infValue = 10.0


    def addNode(self, nodeId):
        if nodeId in self.localRankingMapping:
            return
        else:
            n = len(self.localRankingMapping)
            self.localRankingMapping[ nodeId ] = n
            n += 1
            if n == 1:
                self.localRanking = matrix([1.])
                return
            self.localRanking = hstack([ vstack([ self.localRanking, zeros([1, n - 1]) ]), zeros([n, 1]) ])


    def updateReputation(self, nodeId):
        pass

    def startNewCycle(self):
        self.gossipScoreSteps = 0
        n = len(self.localRankingMapping)
        self.globalRanking = matrix([1.0 / float(n)  ] * len(self.localRankingMapping)).transpose()

    def aggregationCycle(self):
        self.globalReputationCycles += 1
        n = len(self.localRankingMapping)
        normMatrix =matrix([ n, n ])
        for i in range(0, n):
            rowSum = sum(self.localRanking[i])
            for j in range(0, n):
                normMatrix[i][j] =self.localRanking[i][j] / rowSum

        self.lastGlobalRanking = self.globalRanking
        self.globalRanking = normMatrix.transpose() * self.globalRanking


    def getWeightedScore(self, nodeId):
        i = self.localRankingMapping[ nodeId ]
        return self.globalRanking[i] * self.localRanking[i]

    def doAggregation(self):
        self.startNewCycle()
        while(True):
            self.aggregationCycle()
            if self.stopAggregation():
                break

    def stopAggregation(self):
        maxVal = max(self.absmax(self.lastGlobalRanking), self.absmax(self.globalRanking))
        minusMaxVal = max(self.absmax(self.globalRanking - self.lastGlobalRanking))
        return float(minusMaxVal) / float(maxVal) <= self.delta

    def absmax(self, m):
        return max(m.max(), m.min(), key=abs)

    def startGossip(self, nodeId):
        if nodeId not in self.localRankingMapping:
            self.addNode(nodeId)

        j = self.localRankingMapping[ nodeId ]
        n = len(self.localRankingMapping)
        self.weightedScores = [ None ] * n
        self.consensusFactors = [ None ] *n
        self.collectedPairs = [ None ] * n
        self.previousScore = [ None ] * n
        for i in range(0, n):
            self.weightedScores[i] = self.localRanking[i,j] * self.globalRanking[i, 0]
            if i == j:
                self.consensusFactors[i] = 1.0
            else:
                self.consensusFactors[i] = 0.0
            self.previousScore[i] = self.infValue
            self.collectedPairs[ i ] = [[self.weightedScores[i], self.consensusFactors[i]]]
        self.gossipScoreSteps = 0

    def doGossip(self, nodeId):
        self.startGossip(nodeId)

        while True:
            self.gossipStep()
            if self.stop_gossip():
                break


    def stop_gossip (self):
        stop = 0
        if self.gossipScoreSteps >=  self.gossipScoreMaxSteps:
            return True
        for i in range(0, len(self.localRankingMapping)):
            if self.weightedScores[i] == 0:
                newScore = 0.0
            elif self.consensusFactors[i] == 0:
                newScore = self.infValue
            else:
                newScore = float(self.weightedScores [i]) / float(self.consensusFactors[i])
            print "ABS " + str(abs(newScore))
            print "EPSILON " + str(self.epsilon)
            if abs(newScore - self.previousScore[i]) <= self.epsilon:
                print "STOP + 1"
                stop += 1
            self.previousScore[i] = newScore
            print stop
        return stop == len(self.localRankingMapping)

    def gossipStep(self):

        self.gossipScoreSteps += 1
        n = len(self.localRankingMapping)
        for i in range(0, n):
            self.weightedScores[i] = 0.0
            self.consensusFactors[i] = 0.0
            for pair in self.collectedPairs[i]:
                self.weightedScores[i] += pair[0]
                self.consensusFactors[i] += pair[1]
            self.collectedPairs[i] = []

        for i in range(0, n):
            self.collectedPairs[i].append([self.weightedScores[i] / 2.0, self.consensusFactors[i] / 2.0 ])
            r = randint(0, n-1)
            if n > 1:
                while r == i:
                    r = randint(0, n - 1)
            self.collectedPairs[ r ].append([ self.weightedScores[i] / 2.0, self.consensusFactors[i] /2.0 ])

class GossipPositiveNegativeTrustRank:
    def __init__(self, posTrustVal = 1.0, negTrustVal = 2.0, minSumVal = 50):
        self.nodeId = None
        self.positive = GossipTrustRank(selfValue = 1.0)
        self.negative = GossipTrustRank(selfValue = 0.0)
        self.posTrustVal = posTrustVal
        self.negTrustVal = negTrustVal
        self.minSumVal = minSumVal
        self.globVec = {}
        self.gossipNum = 0

    def __str__(self):
        return "[Positive: {}, Negative: {}]".format(self.positive, self.negative)

    def incNodePositive(self, nodeId):
        self.positive.incNodeRank(nodeId)

    def incNodeNegative(self, nodeId):
        self.negative.incNodeRank(nodeId)

    def setNodeId(self, nodeId):
        self.nodeId = nodeId
        self.positive.setNodeId(nodeId)
        self.negative.setNodeId(nodeId)

    def getNodePositive(self, nodeId):
        return self.positive.getNodeRank(nodeId)

    def getNodeNegative(self, nodeId):
        return self.negative.getNodeRank(nodeId)

    def setNodePositive(self, nodeId, value):
        self.positive.setNodeRank(nodeId, value)

    def setNodeNegative(self, nodeId, value):
        self.negative.setNodeRank(nodeId, value)

    def getNodeTrust(self, nodeId):
        pos = self.positive.getNodeRank(nodeId)
        if pos is None:
            pos = 0.0
        neg = self.negative.getNodeRank(nodeId)
        if neg is None:
            neg = 0.0
        val = (self.posTrustVal * pos - self.negTrustVal * neg)
        sumVal = max(self.minSumVal, pos + neg)
        return float(val) / float(sumVal)

    def startAggregation(self):
        self.positive.startAggregation()
        self.negative.startAggregation()

    def stopAggregation(self, finPos, finNeg):
        stopPos = finPos
        stopNeg = finNeg
        if not stopPos:
            stopPos = self.positive.stopAggregation()
        if not stopNeg:
            stopNeg = self.negative.stopAggregation()
        return [ stopPos, stopNeg ]

    def stop_gossip(self, finPos, finNeg):
        stopPos = finPos
        stopNeg = finNeg
        if not stopPos:
            stopPos = self.positive.stop_gossip()
        if not stopNeg:
            stopNeg = self.negative.stop_gossip()
        return [ stopPos, stopNeg ]

    def prepAggregation(self, finPos, finNeg):
        if not finPos:
            self.positive.prepAggregation()
        if not finNeg:
            self.negative.prepAggregation()

    def doGossip(self, finPos, finNeg):
        gossip = [ None, None ]
        if not finPos:
            gossip[0] = self.positive.doGossip()
        if not finNeg:
            gossip[1] = self.negative.doGossip()
        return gossip





class GossipTrustRank:
    def __init__(self, delta = 0.1, epsilon = 0.1, selfValue = 1.0):
        self.nodeId = None
        self.ranking = {}
        self.weightedScore = {}
        self.globVec = {}
        self.prevVec = {}
        self.prevGossipVec = {}
        self.collectedVecs = []
        self.delta = delta
        self.epsilon = epsilon
        self.inf = float("inf")
        self.printData = False
        self.selfValue = selfValue

    def __str__(self):
        return "[Ranking: {}, weightedScore: {}, self.globVec: {}] ".format(self.ranking,
                                                                           self.weightedScore,
                                                                           self.globVec)
    def setNodeId(self, nodeId ):
        self.nodeId = nodeId

    def incNodeRank(self, nodeId):
        val = self.getNodeRank(nodeId)
        if val is not None:
            self.setNodeRank(nodeId, val + 1)
        else:
            self.setNodeRank(nodeId,  1)


    def getNodeRank(self, nodeId):
        if nodeId in self.ranking:
            return self.ranking[ nodeId ]
        else:
            return None

    def getNodeNegative(self, nodeId):
        if nodeId in self.negative:
            return self.negative[ nodeId ]
        else:
            return None

    def setNodeRank(self, nodeId, value):
        self.ranking[ nodeId ] = value

    def startAggregation(self):
        print "startAggregation"
        self.weightedScore = {}
        norm = sum(self.ranking.values())
        n = len(self.ranking)
        for nodeId in self.ranking:
            locTrustValue = float(self.ranking[ nodeId ]) / float(norm)
            self.weightedScore[ nodeId ] = locTrustValue / float(n + 1)

        if n ==  0:
            self.weightedScore[ self.nodeId ] = self.selfValue
        else:
            self.weightedScore[ self.nodeId ] = 1.0 / float(n + 1)

        self.updateGlobVec()

        self.collectedVecs = [ self.globVec ]
        self.prevVec = {}
        self.prevGossipVec = {}

    def prepAggregation (self):
        self.prevVec = self.globVec
        norm = sum(self.ranking.values())
        for nodeId in self.ranking:
            locTrustValue = float(self.ranking[ nodeId ]) / float(norm)
            globVecTrustValue =  self.countDiv(self.globVec[ nodeId ][ 0 ], self.globVec[ nodeId ][ 1 ])
            self.weightedScore[ nodeId ] = locTrustValue * globVecTrustValue
        self.updateGlobVec()

    def countDiv(self, a, b):
        if a == 0.0:
            return 0.0
        if b == 0.0:
            return self.inf
        return float(a) / float(b)


    def stopAggregation(self):
        return self.compareVec(self.globVec, self.prevVec) <= self.delta

    def stop_gossip(self):
        return self.compareVec(self.globVec, self.prevGossipVec) <= self.epsilon

    def compareVec(self, vec1, vec2):
#        print "COMPARE VEC {}, {}".format(vec1, vec2)
        nodes1 = set(vec1.keys())
        nodes2 = set(vec2.keys())
        if set(nodes1) != set(nodes2):
            return self.inf

        val = 0
        for node in nodes1:
            v = self.countDiv(vec1[node][0], vec1[node][1]) - self.countDiv(vec2[node][0], vec2[node][1])
            val += v*v
        return math.sqrt(val)


    def updateGlobVec(self):
        for nodeId, node in self.weightedScore.iteritems():
            if nodeId == self.nodeId:
                self.globVec[ nodeId ] = [ node, 1.0 ]
            else:
                self.globVec[ nodeId ] = [ node, 0.0 ]

    def doGossip(self):
        if self.printData:
            print self.prevGossipVec
        self.prevGossipVec = self.globVec
        if len (self.collectedVecs) > 0:
            self.globVec = {}
        for vec in self.collectedVecs:
            for nodeId, val in vec.iteritems():
                if nodeId not in self.globVec:
                    self.globVec[nodeId] = val
                else:
                    self.globVec[nodeId][0] += val[0]
                    self.globVec[nodeId][1] += val[1]

        self.collectedVecs = []


        vecToSend = {}
        for nodeId, val in self.globVec.iteritems():
            vecToSend[nodeId] = [val[0] / 2.0, val[1] / 2.0 ]

        return [ vecToSend, self.nodeId]

    def hear_gossip(self, gossip):
        if self.printData:
            print "NODE {} hear gossip {}".format(self.nodeId, gossip)
        self.collectedVecs.append(gossip)

    def getNodeTrust(self, nodeId):
        if nodeId in self.globVec:
            return self.countDiv(self.globVec[0], self.globVec[1])
        else:
            return 0.0





