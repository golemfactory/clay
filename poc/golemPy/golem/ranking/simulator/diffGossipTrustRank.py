import math
import random

class LocalRank:
    def __init__( self ):
        self.ranking = {}

    def getNodeRank( self, nodeId ):
        if nodeId in self.ranking:
            return self.ranking[ nodeId ]
        else:
            return None

    def setNodeRank( self, nodeId, value ):
        self.ranking[ nodeId ] = value

    def incNodeRank( self, nodeId ):
        val = self.getNodeRank( nodeId )
        if val is not None:
            self.setNodeRank( nodeId, val + 1)
        else:
            self.setNodeRank(nodeId,  1)


def divTrust( a, b ):
    if a == 0.0:
        return 0.0
    if b == 0.0:
        return float('inf')
    return float( a ) / float( b )


def compareVec( vec1, vec2 ):
    print "COMPARE {} {}".format( vec1, vec2 )
    val = 0
    for node in vec2.keys():
        if node not in vec1.keys():
            return float("inf")
        v = vec1[node] - vec2[node]
        val += v*v
    return math.sqrt( val )


class DiffGossipTrustRank:
    def __init__( self, posTrustVal = 1.0, negTrustVal = 2.0, minSumVal = 50, epsilon = 0.01  ):
        self.nodeId = None
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

    def __str__( self ):
        return "globVec: {}".format(self.globVec )

    def incNodePositive( self, nodeId ):
        self.positive.incNodeRank( nodeId )

    def incNodeNegative( self, nodeId ):
        self.negative.incNodeRank( nodeId )

    def setNodeId( self, nodeId ):
        self.nodeId = nodeId

    def getNodePositive( self, nodeId ):
        return self.positive.getNodeRank( nodeId )

    def getNodeNegative( self, nodeId ):
        return self.negative.getNodeRank( nodeId )

    def setNodePositive( self, nodeId, value ):
        self.positive.setNodeRank( nodeId, value )

    def setNodeNegative( self, nodeId, value ):
        self.negative.setNodeRank( nodeId, value )

    def isStopped( self ):
        return self.stop

    def getNodeTrust( self, nodeId ):
        pos = self.positive.getNodeRank( nodeId )
        if pos is None:
            pos = 0.0
        neg = self.negative.getNodeRank( nodeId )
        if neg is None:
            neg = 0.0
        val = ( self.posTrustVal * pos - self.negTrustVal * neg )
        sumVal = max( self.minSumVal, pos + neg )
        return max(min( float( val ) / float( sumVal ), 1.0), -1.0)

    def startDiffGossip( self, k ):
        self.gossipNum = k
        self.workingVec = {}
        self.stop = False
        self.globalStop = False
        knownNodes = set( self.positive.ranking.keys() + self.negative.ranking.keys())
        for node in knownNodes:
            self.workingVec[node] = [self.getNodeTrust( node ), 1.0, 0.0]
        for node in self.globVec:
            if node not in knownNodes:
                self.workingVec[ node ] = [ 0.0, 0.0, 0.0 ]
        if len( self.workingVec ) > 0:
            randNode = random.sample( self.workingVec.keys(), 1 )[0]
            self.workingVec[ randNode ][1] = 1.0
        for node, val in self.workingVec.iteritems():
            self.globVec[ node ] = divTrust( val[0], val[1] )
        self.collectedVecs = [ self.workingVec ]


    def doGossip (self ):

        if self.globalStop:
            return []
        self.workingVec = {}
        for vec in self.collectedVecs:
            for nodeId, val in vec.iteritems():
                if nodeId not in self.workingVec:
                    self.workingVec[ nodeId ] = val
                else:
                    self.workingVec[ nodeId ][0] += val[0]
                    self.workingVec[ nodeId ][1] += val[1]
                    self.workingVec[ nodeId ][2] += val[2]

        self.collectedVecs = []

        vecToSend = {}
        for nodeId, val in self.workingVec.iteritems():
            vecToSend[ nodeId ] = [ val[0] / (self.gossipNum), val[1] / ( self.gossipNum), val[2] / (self.gossipNum) ]


        return [ vecToSend, self.nodeId ]


    def hearGossip( self, gossip ):
        self.collectedVecs.append( gossip )

    def getGlobalVal(self, nodeId ):
        if nodeId in self.globVec:
            return self.globVec[ nodeId ]
        return None

    def stopGossip( self ):
        if self.stop:
            return True
        else:
            newGlobVec = {}
            for node, val in self.workingVec.iteritems():
                newGlobVec[node] = divTrust( val[0], val[1] )
            if compareVec( self.globVec, newGlobVec ) < self.epsilon:
                self.stop = True
            for node, val in newGlobVec.iteritems():
                self.globVec[node] = val
            return self.stop

    def neighStopped( self ):
        self.globalStop = True