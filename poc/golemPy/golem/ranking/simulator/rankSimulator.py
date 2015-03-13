import sys
import os
import random
from copy import copy

sys.path.append( os.environ.get( 'GOLEM' ) )

from golem.ranking.simpleRank import SimpleRank
from networkSimulator import PANetworkSimulator

class RankSimulator:
    def __init__( self, rankClass, optPeers = 2, network = PANetworkSimulator ):
        self.network = network()
        self.ranking = {}
        self.behaviour = {}
        self.nodesCnt = 0
        self.rankClass = rankClass
        self.optPeers = optPeers
        self.lastNode = None

    def getLastNodeName( self ):
        return self.lastNode

    def addNode( self, goodNode = True ):
        node = self.network.addNode()
        self.ranking[ node ] = self.rankClass()
        self.behaviour[ node ] = goodNode
        self.lastNode = node

    def fullAddNode( self, goodNode = True ):
        self.addNode( goodNode )
        self.syncNetwork()

    def connectNode( self, node ):
        self.network.connectNode( node )

    def syncNetwork( self ):
        self.network.syncNetwork( self.optPeers )

    def printState( self ):
        for node, nodeData in self.network.nodes.iteritems():
            print "{}: {}, peers {}\n".format( node, self.ranking[node], nodeData )

    def startTask( self, node ):
        if node not in self.ranking:
            print "Wrong node {}".format( node )

        countingNodes = self.ranking.keys()
        for n in random.sample( countingNodes, self.numNodesTask() ):
            if n != node:
                if self.askForNodeDelegating( n, node ) and self.askForNodeComputing( node, n ):
                    self.countTask( n, node )

    def askForNodeDelegating( self, cntNode, dntNode ):
        return True

    def askForNodeComputing( self, cntNode, dntNode ):
        return True

    def numNodesTask(self):
        return 3

    def countTask(self, cntNode, dntNode ):
        if cntNode not in self.ranking:
            print "Wrong node {}".format( cntNode )
        if dntNode not in self.ranking:
            print "Wrong node {}".format( dntNode )

        if self.behaviour[cntNode]:
            self.goodCounting(cntNode, dntNode )
            if self.behaviour[dntNode]:
                self.goodPayment( cntNode, dntNode )
            else:
                self.noPayment( cntNode, dntNode )
        else:
            self.badCounting( cntNode, dntNode )


    def goodCounting( self, cntNode, dntNode ):
        pass

    def badCounting( self, cntNode, dntNode ):
        pass

    def goodPayment( self, cntNode, dntNode ):
        pass

    def noPayment( self, cntNode, dntNode ):
        pass



class SimpleRankSimulator( RankSimulator ):
    def __init__( self, optPeers = 3, trustThreshold  = 0.2, nodesForTask = 2, goodTaskReward = 0.1,
                  badTaskPunishment = 0.2, paymentReward = 0.2, badPaymentPunishment = 0.3 ):
        RankSimulator.__init__( self, SimpleRank, optPeers )
        self.trustThreshold = trustThreshold
        self.nodesForTask = nodesForTask
        self.goodTaskReward = goodTaskReward
        self.badTaskPunishment = badTaskPunishment
        self.paymentReward = paymentReward
        self.badPaymentPunishment = badPaymentPunishment

    def numNodesTask(self):
        return self.nodesForTask

    def goodCounting( self, cntNode, dntNode ):
        self.addToRank( dntNode, cntNode, self.goodTaskReward )

    def badCounting( self, cntNode, dntNode ):
        self.addToRank( dntNode, cntNode, - self.badTaskPunishment )
        self.addToRank( cntNode, dntNode, - self.badPaymentPunishment )

    def goodPayment( self, cntNode, dntNode ):
        self.addToRank( cntNode, dntNode, self.paymentReward )

    def noPayment( self, cntNode, dntNode ):
        self.addToRank( cntNode, dntNode, -self.badPaymentPunishment )

    def addToRank(self, inNode, forNode, value ):
        self.ranking[inNode].setNodeRank(forNode, self.getGlobalRank(inNode, forNode) + value )

    def askForNodeDelegating( self, cntNode, dntNode ):
        return self.askForNode( cntNode, dntNode )

    def askForNodeComputing( self, dntNode, cntNode ):
        return self.askForNode( dntNode, cntNode )

    def askForNode( self, node, forNode ):
        if node not in self.ranking:
            print "Wrong node {}".format( node )
        if forNode not in self.ranking:
            print "Wrong node {}".format( forNode )

        otherRank = {}
        for peer in self.network.nodes[node]:
            otherRank[peer] = self.ranking[peer].getNodeRank( forNode )

        test = self.ranking[node].globalNodeRank( forNode, otherRank )
        if test > self.trustThreshold:
            return True
        else:
            if forNode in self.network.nodes[node]:
                self.network.nodes[node].remove( forNode )
            return False

    def getGlobalRank(self, node, forNode ):
        otherRank = {}
        for peer in self.network.nodes[node]:
            otherRank[peer] = self.ranking[peer].getNodeRank( forNode )

        return self.ranking[node].globalNodeRank( forNode, otherRank )


def main():
    rs = SimpleRankSimulator()
    for i in range(0, 5):
        rs.fullAddNode( goodNode = False )
    for i in range(0, 10):
        rs.fullAddNode( goodNode = True )

    rs.printState()
    print "################"
    for i in range(0, 200):
        rs.startTask( random.sample( rs.ranking.keys(), 1)[0] )
    rs.printState()


if __name__ == "__main__":
    main()

