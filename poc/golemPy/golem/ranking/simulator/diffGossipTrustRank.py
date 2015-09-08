import math
import random

class LocalRank:
    def __init__(self):
        self.ranking = {}

    def getNodeRank(self, node_id):
        if node_id in self.ranking:
            return self.ranking[ node_id ]
        else:
            return None

    def setNodeRank(self, node_id, value):
        self.ranking[ node_id ] = value

    def incNodeRank(self, node_id):
        val = self.getNodeRank(node_id)
        if val is not None:
            self.setNodeRank(node_id, val + 1)
        else:
            self.setNodeRank(node_id,  1)


def divTrust(a, b):
    if a == 0.0:
        return 0.0
    if b == 0.0:
        return float('inf')
    return float(a) / float(b)


def compareVec(vec1, vec2):
    print "COMPARE {} {}".format(vec1, vec2)
    val = 0
    for node in vec2.keys():
        if node not in vec1.keys():
            return float("inf")
        v = vec1[node] - vec2[node]
        val += v*v
    return math.sqrt(val)


class DiffGossipTrustRank:
    def __init__(self, posTrustVal = 1.0, negTrustVal = 2.0, minSumVal = 50, epsilon = 0.01 ):
        self.node_id = None
        self.positive = LocalRank()
        self.negative = LocalRank()

        self.posTrustVal = posTrustVal
        self.negTrustVal = negTrustVal
        self.minSumVal = minSumVal
        self.epsilon = epsilon

        self.gossipNum = 0
        self.globVec = {}
        self.workingVec = {}
        self.collectedVecs = []
        self.globalStop = False
        self.stop = False

    def __str__(self):
        return "globVec: {}".format(self.globVec)

    def incNodePositive(self, node_id):
        self.positive.incNodeRank(node_id)

    def incNodeNegative(self, node_id):
        self.negative.incNodeRank(node_id)

    def setNodeId(self, node_id):
        self.node_id = node_id

    def getNodePositive(self, node_id):
        return self.positive.getNodeRank(node_id)

    def getNodeNegative(self, node_id):
        return self.negative.getNodeRank(node_id)

    def setNodePositive(self, node_id, value):
        self.positive.setNodeRank(node_id, value)

    def setNodeNegative(self, node_id, value):
        self.negative.setNodeRank(node_id, value)

    def isStopped(self):
        return self.stop

    def getNodeTrust(self, node_id):
        pos = self.positive.getNodeRank(node_id)
        if pos is None:
            pos = 0.0
        neg = self.negative.getNodeRank(node_id)
        if neg is None:
            neg = 0.0
        val = (self.posTrustVal * pos - self.negTrustVal * neg)
        sumVal = max(self.minSumVal, pos + neg)
        return max(min(float(val) / float(sumVal), 1.0), -1.0)

    def startDiffGossip(self, k):
        self.gossipNum = k
        self.workingVec = {}
        self.stop = False
        self.globalStop = False
        knownNodes = set(self.positive.ranking.keys() + self.negative.ranking.keys())
        for node in knownNodes:
            self.workingVec[node] = [self.getNodeTrust(node), 1.0, 0.0]
        for node in self.globVec:
            if node not in knownNodes:
                self.workingVec[ node ] = [ 0.0, 0.0, 0.0 ]
        if len(self.workingVec) > 0:
            randNode = random.sample(self.workingVec.keys(), 1)[0]
            self.workingVec[ randNode ][1] = 1.0
        for node, val in self.workingVec.iteritems():
            self.globVec[ node ] = divTrust(val[0], val[1])
        self.collectedVecs = [ self.workingVec ]


    def doGossip (self):

        if self.globalStop:
            return []
        self.workingVec = {}
        for vec in self.collectedVecs:
            for node_id, val in vec.iteritems():
                if node_id not in self.workingVec:
                    self.workingVec[ node_id ] = val
                else:
                    self.workingVec[ node_id ][0] += val[0]
                    self.workingVec[ node_id ][1] += val[1]
                    self.workingVec[ node_id ][2] += val[2]

        self.collectedVecs = []

        vecToSend = {}
        for node_id, val in self.workingVec.iteritems():
            vecToSend[ node_id ] = [ val[0] / (self.gossipNum), val[1] / (self.gossipNum), val[2] / (self.gossipNum) ]


        return [ vecToSend, self.node_id ]


    def hear_gossip(self, gossip):
        self.collectedVecs.append(gossip)

    def getGlobalVal(self, node_id):
        if node_id in self.globVec:
            return self.globVec[ node_id ]
        return None

    def stop_gossip(self):
        if self.stop:
            return True
        else:
            newGlobVec = {}
            for node, val in self.workingVec.iteritems():
                newGlobVec[node] = divTrust(val[0], val[1])
            if compareVec(self.globVec, newGlobVec) < self.epsilon:
                self.stop = True
            for node, val in newGlobVec.iteritems():
                self.globVec[node] = val
            return self.stop

    def neighStopped(self):
        self.globalStop = True