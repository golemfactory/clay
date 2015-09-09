from numpy import zeros, hstack, vstack, matrix
import math
from random import randint, sample

class GossipTrustTest:
    def __init__(self, epsilon = 0.1, delta = 0.1, goosip_score_max_steps = 10000, aggregation_max_steps = 4):
        self.local_ranking = None
        self.local_rankingMapping = {}
        self.lastGlobalRanking = None
        self.globalRanking = None
        self.epsilon = epsilon
        self.delta = delta
        self.gossipScoreSteps = 0
        self.goosip_score_max_steps = goosip_score_max_steps
        self.aggregationSteps = 0
        self.aggregation_max_steps = aggregation_max_steps
        self.globalReputationCycles = 0
        #self.outerSend = outerSender
        self.weightedScores = None
        self.consensusFactors = None
        self.collectedPairs = None
        self.previousScore = None
        self.infValue = 10.0


    def addNode(self, node_id):
        if node_id in self.local_rankingMapping:
            return
        else:
            n = len(self.local_rankingMapping)
            self.local_rankingMapping[ node_id ] = n
            n += 1
            if n == 1:
                self.local_ranking = matrix([1.])
                return
            self.local_ranking = hstack([ vstack([ self.local_ranking, zeros([1, n - 1]) ]), zeros([n, 1]) ])


    def updateReputation(self, node_id):
        pass

    def start_new_cycle(self):
        self.gossipScoreSteps = 0
        n = len(self.local_rankingMapping)
        self.globalRanking = matrix([1.0 / float(n)  ] * len(self.local_rankingMapping)).transpose()

    def aggregationCycle(self):
        self.globalReputationCycles += 1
        n = len(self.local_rankingMapping)
        normMatrix =matrix([ n, n ])
        for i in range(0, n):
            rowSum = sum(self.local_ranking[i])
            for j in range(0, n):
                normMatrix[i][j] =self.local_ranking[i][j] / rowSum

        self.lastGlobalRanking = self.globalRanking
        self.globalRanking = normMatrix.transpose() * self.globalRanking


    def getWeightedScore(self, node_id):
        i = self.local_rankingMapping[ node_id ]
        return self.globalRanking[i] * self.local_ranking[i]

    def doAggregation(self):
        self.start_new_cycle()
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

    def start_gossip(self, node_id):
        if node_id not in self.local_rankingMapping:
            self.addNode(node_id)

        j = self.local_rankingMapping[ node_id ]
        n = len(self.local_rankingMapping)
        self.weightedScores = [ None ] * n
        self.consensusFactors = [ None ] *n
        self.collectedPairs = [ None ] * n
        self.previousScore = [ None ] * n
        for i in range(0, n):
            self.weightedScores[i] = self.local_ranking[i,j] * self.globalRanking[i, 0]
            if i == j:
                self.consensusFactors[i] = 1.0
            else:
                self.consensusFactors[i] = 0.0
            self.previousScore[i] = self.infValue
            self.collectedPairs[ i ] = [[self.weightedScores[i], self.consensusFactors[i]]]
        self.gossipScoreSteps = 0

    def doGossip(self, node_id):
        self.start_gossip(node_id)

        while True:
            self.gossipStep()
            if self.stop_gossip():
                break


    def stop_gossip (self):
        stop = 0
        if self.gossipScoreSteps >=  self.goosip_score_max_steps:
            return True
        for i in range(0, len(self.local_rankingMapping)):
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
        return stop == len(self.local_rankingMapping)

    def gossipStep(self):

        self.gossipScoreSteps += 1
        n = len(self.local_rankingMapping)
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
        self.node_id = None
        self.positive = GossipTrustRank(selfValue = 1.0)
        self.negative = GossipTrustRank(selfValue = 0.0)
        self.posTrustVal = posTrustVal
        self.negTrustVal = negTrustVal
        self.minSumVal = minSumVal
        self.globVec = {}
        self.gossipNum = 0

    def __str__(self):
        return "[Positive: {}, Negative: {}]".format(self.positive, self.negative)

    def incNodePositive(self, node_id):
        self.positive.incNodeRank(node_id)

    def incNodeNegative(self, node_id):
        self.negative.incNodeRank(node_id)

    def setNodeId(self, node_id):
        self.node_id = node_id
        self.positive.setNodeId(node_id)
        self.negative.setNodeId(node_id)

    def getNodePositive(self, node_id):
        return self.positive.getNodeRank(node_id)

    def getNodeNegative(self, node_id):
        return self.negative.getNodeRank(node_id)

    def setNodePositive(self, node_id, value):
        self.positive.setNodeRank(node_id, value)

    def setNodeNegative(self, node_id, value):
        self.negative.setNodeRank(node_id, value)

    def getNodeTrust(self, node_id):
        pos = self.positive.getNodeRank(node_id)
        if pos is None:
            pos = 0.0
        neg = self.negative.getNodeRank(node_id)
        if neg is None:
            neg = 0.0
        val = (self.posTrustVal * pos - self.negTrustVal * neg)
        sumVal = max(self.minSumVal, pos + neg)
        return float(val) / float(sumVal)

    def start_aggregation(self):
        self.positive.start_aggregation()
        self.negative.start_aggregation()

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
        self.node_id = None
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
    def setNodeId(self, node_id ):
        self.node_id = node_id

    def incNodeRank(self, node_id):
        val = self.getNodeRank(node_id)
        if val is not None:
            self.setNodeRank(node_id, val + 1)
        else:
            self.setNodeRank(node_id,  1)


    def getNodeRank(self, node_id):
        if node_id in self.ranking:
            return self.ranking[ node_id ]
        else:
            return None

    def getNodeNegative(self, node_id):
        if node_id in self.negative:
            return self.negative[ node_id ]
        else:
            return None

    def setNodeRank(self, node_id, value):
        self.ranking[ node_id ] = value

    def start_aggregation(self):
        print "start_aggregation"
        self.weightedScore = {}
        norm = sum(self.ranking.values())
        n = len(self.ranking)
        for node_id in self.ranking:
            locTrustValue = float(self.ranking[ node_id ]) / float(norm)
            self.weightedScore[ node_id ] = locTrustValue / float(n + 1)

        if n ==  0:
            self.weightedScore[ self.node_id ] = self.selfValue
        else:
            self.weightedScore[ self.node_id ] = 1.0 / float(n + 1)

        self.updateGlobVec()

        self.collectedVecs = [ self.globVec ]
        self.prevVec = {}
        self.prevGossipVec = {}

    def prepAggregation (self):
        self.prevVec = self.globVec
        norm = sum(self.ranking.values())
        for node_id in self.ranking:
            locTrustValue = float(self.ranking[ node_id ]) / float(norm)
            globVecTrustValue =  self.count_div(self.globVec[ node_id ][ 0 ], self.globVec[ node_id ][ 1 ])
            self.weightedScore[ node_id ] = locTrustValue * globVecTrustValue
        self.updateGlobVec()

    def count_div(self, a, b):
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
            v = self.count_div(vec1[node][0], vec1[node][1]) - self.count_div(vec2[node][0], vec2[node][1])
            val += v*v
        return math.sqrt(val)


    def updateGlobVec(self):
        for node_id, node in self.weightedScore.iteritems():
            if node_id == self.node_id:
                self.globVec[ node_id ] = [ node, 1.0 ]
            else:
                self.globVec[ node_id ] = [ node, 0.0 ]

    def doGossip(self):
        if self.printData:
            print self.prevGossipVec
        self.prevGossipVec = self.globVec
        if len (self.collectedVecs) > 0:
            self.globVec = {}
        for vec in self.collectedVecs:
            for node_id, val in vec.iteritems():
                if node_id not in self.globVec:
                    self.globVec[node_id] = val
                else:
                    self.globVec[node_id][0] += val[0]
                    self.globVec[node_id][1] += val[1]

        self.collectedVecs = []


        vecToSend = {}
        for node_id, val in self.globVec.iteritems():
            vecToSend[node_id] = [val[0] / 2.0, val[1] / 2.0 ]

        return [ vecToSend, self.node_id]

    def hear_gossip(self, gossip):
        if self.printData:
            print "NODE {} hear gossip {}".format(self.node_id, gossip)
        self.collectedVecs.append(gossip)

    def getNodeTrust(self, node_id):
        if node_id in self.globVec:
            return self.count_div(self.globVec[0], self.globVec[1])
        else:
            return 0.0





