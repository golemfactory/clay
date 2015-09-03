import sys
import os
import random
from  numpy import matrix
from collections import OrderedDict
sys.path.append(os.environ.get('GOLEM'))

from golem.ranking.gossipTrustRank import GossipTrustTest, GossipPositiveNegativeTrustRank
from rankSimulator import RankSimulator


class GossipTrustNodeRank:
    def __init__(self):
        self.computing = GossipPositiveNegativeTrustRank()
        self.delegating = GossipPositiveNegativeTrustRank()
        self.nodeId = None

    def setNodeId(self, nodeId):
        self.nodeId = nodeId
        self.computing.setNodeId(nodeId)
        self.delegating.setNodeId(nodeId)

    def setSeedRank(self, seedNode):
        pass

    def __str__(self):
        return "Computing: {}, ".format(self.computing) +"Delegating: {} ".format(self.delegating)

    def startAggregation(self):
        self.computing.startAggregation()
        self.delegating.startAggregation()

    def stopAggregation(self, finished, stop):
        [stopPos, stopNeg] = self.computing.stopAggregation(finished[0], finished[1])
        if stopPos:
            stop[0] += 1
        if stopNeg:
            stop[1] += 1
        [stopPos, stopNeg] = self.computing.stopAggregation(finished[2], finished[3])
        if stopPos:
            stop[2] += 1
        if stopNeg:
            stop[3] += 1

    def stop_gossip(self, finished, stop):
        [stopPos, stopNeg] = self.computing.stop_gossip(finished[0], finished[1])
        if stopPos:
            stop[0] += 1
        if stopNeg:
            stop[1] += 1
        [stopPos, stopNeg] = self.computing.stop_gossip(finished[2], finished[3])
        if stopPos:
            stop[2] += 1
        if stopNeg:
            stop[3] += 1

    def prepAggregation(self, finished):
        self.computing.prepAggregation(finished[0], finished[1])
        self.delegating.prepAggregation(finished[2], finished[3])

    def doGossip(self, finished):
        gossip = [None, None ]
        gossip[0] = self.computing.doGossip(finished[0], finished[1])
        gossip[1] = self.delegating.doGossip(finished[2], finished[3])
        return gossip



class GossipTrustSimulator(RankSimulator):
    def __init__(self, optPeers = 3, aggMaxSteps = 3, gossipMaxSteps = 3):
        RankSimulator.__init__(self, GossipTrustNodeRank, optPeers)
        self.globalRanks = {}
        self.aggMaxSteps = aggMaxSteps
        self.gossipMaxSteps = gossipMaxSteps
        self.aggSteps = 0
        self.gossipSteps = 0
        self.finished = [ False ] * 4
        self.finishedGossips = [ False ] * 4

    def addNode(self, goodNode = True):
        RankSimulator.addNode(self, goodNode)
        nodeId = 'node{}'.format(str(self.nodesCnt).zfill(3))
        self.nodes[ nodeId ]['globalRanking'] = {}
        self.nodes[ nodeId ]['ranking'].setNodeId(nodeId)
        self.nodes[ nodeId ]['ranking'].computing.negative.printData = True

    def goodCounting(self, cntNode, dntNode):
        self.nodes[ dntNode ]['ranking'].computing.incNodePositive(cntNode)

    def badCounting(self, cntNode, dntNode):
        self.nodes[ dntNode ]['ranking'].computing.incNodeNegative(cntNode)
        self.nodes[ cntNode ]['ranking'].delegating.incNodeNegative(dntNode)

    def goodPayment(self, cntNode, dntNode):
        self.nodes[ cntNode ]['ranking'].delegating.incNodePositive(dntNode)

    def noPayment(self, cntNode, dntNode):
        self.nodes[ cntNode ]['ranking'].delegating.incNodeNegative(dntNode)

    def askForNodeComputing(self, cntNode, dntNode):
        return True
       # return self.nodes[dntNode]['ranking'].computing.negative.getNodeTrust(cntNode) < 1.0

    def askForNodeDelegating(self, cntNode, dntNode):
        return True
      #  return self.nodes[cntNode]['ranking'].delegating.negative.getNodeTrust(dntNode) < 1.0

    def syncRanking(self):
        print "SYNC RANKING"
        while True:
            self.doAggregationStep()
            if self.stopAggregation():
                break
            self.aggSteps += 1
            if self.aggSteps >= self.aggMaxSteps:
                break
        print "AGG STEP {}".format(self.aggSteps)
        self.aggSteps = 0

    def startAggregation(self):
        for nodeId, node in self.nodes.iteritems():
            node['ranking'].startAggregation()
        self.finished = [ False, False, False, False ]
        self.aggSteps = 0

    def stopAggregation(self):
        stop = [0, 0, 0, 0]
        for nodeId, node in self.nodes.iteritems():
            node['ranking'].stopAggregation(self.finished, stop)
        for i in range(0, 4):
            if stop[i] == len(self.nodes):
                self.finished[i] = True
        for i in range(0, 4):
            if not self.finished[i]:
                return False
        return True

    def prepAggregation(self):
        for nodeId, node in self.nodes.iteritems():
            node['ranking'].prepAggregation(self.finished)
        self.gossipSteps = 0
        self.finishedGossips = self.finished

    def doAggregationStep(self):
        if self.aggSteps == 0:
            self.startAggregation()
        else:
            self.prepAggregation()

        while True:
            self.doGossip()
            if self.stop_gossip():
                break
            self.gossipSteps += 1
            if self.gossipSteps >= self.gossipMaxSteps:
                break
        print "GOSSIP STEP {}".format(self.gossipSteps)
        self.gossipSteps = 0

    def stop_gossip(self):
        stop = [0, 0, 0, 0]
        for nodeId, node in self.nodes.iteritems():
            node['ranking'].stop_gossip(self.finishedGossips, stop)
        same = self.sameVec()
        for i in range(0, 4):
            if stop[i] == len(self.nodes) and same[i]:
                self.finishedGossips[i] = True
        for i in range(0, 4):
            if not self.finishedGossips[i]:
                return False
        return True


    def sameVec(self) :
        vec = [{}, {}, {}, {}]
        ret = [ None, None, None, None]
        for nodeId, node in self.nodes.iteritems():
            for globNodeId, globVal in node['ranking'].computing.positive.globVec.iteritems():
                if globNodeId not in vec[0]:
                    vec[0][ globNodeId ] = countDiv(globVal[0], globVal[1])
                else:
                    if abs(vec[0][ globNodeId ] - countDiv(globVal[0], globVal[1])) > 0.1:
                        ret[ 0 ] = False
                        break
            for globNodeId, globVal in node['ranking'].computing.negative.globVec.iteritems():
                if globNodeId not in vec[1]:
                    vec[1][ globNodeId ] = countDiv(globVal[0], globVal[1])
                else:
                    if abs(vec[1][ globNodeId ] - countDiv(globVal[0], globVal[1])) > 0.1:
                        ret[ 1 ] = False
                        break
            for globNodeId, globVal in node['ranking'].delegating.positive.globVec.iteritems():
                if globNodeId not in vec[2]:
                    vec[2][ globNodeId ] = countDiv(globVal[0], globVal[1])
                else:
                    if abs(vec[2][ globNodeId ] - countDiv(globVal[0], globVal[1])) > 0.1:
                        ret[ 2 ] = False
                        break
            for globNodeId, globVal in node['ranking'].delegating.negative.globVec.iteritems():
                if globNodeId not in vec[3]:
                    vec[3][ globNodeId ] = countDiv(globVal[0], globVal[1])
                else:
                    if abs(vec[3][ globNodeId ] - countDiv(globVal[0], globVal[1])) > 0.1:
                        ret[ 3 ] = False
                        break
        for i in range(0, 4):
            if ret[i] is None:
                ret[i] = True
        return ret


    def countDiv(self, a, b):
        if a == 0.0:
            return 0.0
        if b == 0.0:
            return float("inf")
        return float(a) / float(b)

    def doGossip(self):
        gossips = []

        for nodeId, node in self.nodes.iteritems():
            gossips.append(node['ranking'].doGossip(self.finishedGossips))

        self.send_gossips(gossips)

    def send_gossips(self, gossips):
        for gossip in gossips:
            if gossip[0] is not None:
                if gossip[0][0] is not None:
                    gossipVec, node1 = gossip[0][0]
                    node2 = self.getSecondNode(node1)
                    self.nodes[node1]['ranking'].computing.positive.hear_gossip(gossipVec)
                    self.nodes[node2]['ranking'].computing.positive.hear_gossip(gossipVec)
                if gossip[0][1] is not None:
                    gossipVec, node1 = gossip[0][1]
                    node2 = self.getSecondNode(node1)
                    self.nodes[node1]['ranking'].computing.negative.hear_gossip(gossipVec)
                    self.nodes[node2]['ranking'].computing.negative.hear_gossip(gossipVec)
            if gossip[1] is not None:
                if gossip[1][0] is not None:
                    gossipVec, node1 = gossip[1][0]
                    node2 = self.getSecondNode(node1)
                    self.nodes[node1]['ranking'].delegating.positive.hear_gossip(gossipVec)
                    self.nodes[node2]['ranking'].delegating.positive.hear_gossip(gossipVec)
                if gossip[1][1] is not None:
                    gossipVec, node1 = gossip[1][1]
                    node2 = self.getSecondNode(node1)
                    self.nodes[node1]['ranking'].delegating.negative.hear_gossip(gossipVec)
                    self.nodes[node2]['ranking'].delegating.negative.hear_gossip(gossipVec)

    def getSecondNode(self, node1):
        r = random.sample(self.nodes.keys(), 1)
        if len(self.nodes) > 1:
            while r == node1:
                r = random.sample(self.nodes.keys(), 1)
        return r[0]


def countDiv(a, b):
    if a == 0.0:
        return 0.0
    if b == 0.0:
        return float("inf")
    return float(a) / float(b)

def makeGossipTrustTest():
    gtr = GossipTrustTest(delta = 0.1)
    gtr.addNode('abc')
    gtr.addNode('def')
    gtr.addNode('ghi')
    print gtr.localRanking
    print gtr.localRankingMapping
    print gtr.globalRanking
    gtr.localRanking[0,1] = 0.2
    gtr.localRanking[1,1] = 0
    gtr.localRanking[2,1] = 0.6
    print gtr.localRanking
    gtr.globalRanking = matrix([[1.0/2.0], [1.0/3.0], [1.0/6.0 ]])
    print gtr.globalRanking
    gtr.doGossip('def')
    print gtr.previousScore
    print gtr.weightedScores
    print gtr.consensusFactors
    print [gtr.weightedScores[i] / gtr.consensusFactors[i] for i in range(0,3)]
    print gtr.gossipScoreSteps

def main():
    rs = GossipTrustSimulator()
    for i in range(0, 1):
        rs.fullAddNode(goodNode = False)
    for i in range(0, 2):
        rs.fullAddNode(goodNode = True)

    rs.printState()
    print "################"
    for i in range(0, 3):
        rs.startTask(random.sample(rs.nodes.keys(), 1)[0])
      #  rs.syncRanking()
    rs.printState()
    rs.syncRanking()
    rs.printState()
    print "Positive"
    nd = OrderedDict(sorted(rs.nodes.items(), key=lambda t: t[0]))
    for nodeId, node in nd.iteritems():
        d = OrderedDict(sorted(node['ranking'].computing.positive.globVec.items(), key=lambda t: t[0]))
        for nId, val in d.iteritems():
            d[nId] = countDiv(val[0], val[1])
        print "{}: {}\n".format(nodeId, d)

    print "Negative"
    for nodeId, node in nd.iteritems():
        d = OrderedDict(sorted(node['ranking'].computing.negative.globVec.items(), key=lambda t: t[0]))
        for nId, val in d.iteritems():
            d[nId] = countDiv(val[0], val[1])
        print "{}: {}\n".format(nodeId, d)



if __name__ == "__main__":
    main()
