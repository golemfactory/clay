import sys
import os
import random
from copy import copy

sys.path.append( os.environ.get( 'GOLEM' ) )

from golem.ranking.simpleRank import SimpleRank

class RankSimulator:
    def __init__( self, rankClass, optPeers = 3 ):
        self.nodes = {}
        self.nodesCnt = 0
        self.rankClass = rankClass
        self.optPeers = optPeers

    def addNode( self, goodNode = True ):
        self.nodesCnt += 1
        self.nodes['node{}'.format( str( self.nodesCnt ).zfill(3 ))] = {'ranking': self.rankClass(), 'peers': set(), 'good': goodNode }

    def fullAddNode( self, goodNode = True ):
        self.addNode( goodNode )
        self.connectNode( "node{}".format( str( self.nodesCnt ).zfill(3 ) ) )
        self.syncNetwork()

    def connectNode( self, node ):
        if node not in self.nodes:
            print "Wrong node {}".format( node )

        if self.nodesCnt > 1:
            while True:
                seedNode = random.sample( self.nodes.keys(), 1 )[0]
                if seedNode != node:
                    break
            self.nodes[ seedNode ][ 'peers' ].add( node )
            self.nodes[ node ]['ranking'].setSeedRank( seedNode )
            self.nodes[ node ][ 'peers' ].add( seedNode )

    def syncNetwork( self ):
        for node, nodeData in self.nodes.iteritems():
            if len( nodeData['peers'] ) < self.optPeers:
                newPeers = set()
                for peer in copy( nodeData['peers'] ):
                    if len( self.nodes[node]['peers'] ) < self.optPeers:
                        self.nodes[node]['peers'] |= self.nodes[peer]['peers']
                        if node in self.nodes[ node ]['peers']:
                            self.nodes[ node ]['peers'].remove( node )

    def printState( self ):
        for node, nodeData in self.nodes.iteritems():
            print "{}: {}, peers {}\n".format( node, nodeData['ranking'], nodeData['peers'] )

    def startTask( self, node ):
        if node not in self.nodes:
            print "Wrong node {}".format( node )

        countingNodes = self.nodes.keys()
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
        if cntNode not in self.nodes:
            print "Wrong node {}".format( cntNode )
        if dntNode not in self.nodes:
            print "Wrong node {}".format( dntNode )

        if self.nodes[cntNode]['good']:
            self.goodCounting(cntNode, dntNode )
            if self.nodes[dntNode]['good']:
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
        self.nodes[inNode]['ranking'].setNodeRank(forNode, self.getGlobalRank(inNode, forNode) + value )

    def askForNodeDelegating( self, cntNode, dntNode ):
        return self.askForNode( cntNode, dntNode )

    def askForNodeComputing( self, dntNode, cntNode ):
        return self.askForNode( dntNode, cntNode )

    def askForNode( self, node, forNode ):
        if node not in self.nodes:
            print "Wrong node {}".format( node )
        if forNode not in self.nodes:
            print "Wrong node {}".format( forNode )

        otherRank = {}
        for peer in self.nodes[node]['peers']:
            otherRank[peer] = self.nodes[peer]['ranking'].getNodeRank( forNode )

        test = self.nodes[node]['ranking'].globalNodeRank( forNode, otherRank )
        if test > self.trustThreshold:
            return True
        else:
            if forNode in self.nodes[node]['peers']:
                self.nodes[node]['peers'].remove( forNode )
            return False

    def getGlobalRank(self, node, forNode ):
        otherRank = {}
        for peer in self.nodes[node]['peers']:
            otherRank[peer] = self.nodes[peer]['ranking'].getNodeRank( forNode )

        return self.nodes[node]['ranking'].globalNodeRank( forNode, otherRank )


def main():
    rs = SimpleRankSimulator()
    for i in range(0, 5):
        rs.fullAddNode( goodNode = False )
    for i in range(0, 25):
        rs.fullAddNode( goodNode = True )

    rs.printState()
    print "################"
    for i in range(0, 200):
        rs.startTask( random.sample( rs.nodes.keys(), 1)[0] )
    rs.printState()


if __name__ == "__main__":
    main()

