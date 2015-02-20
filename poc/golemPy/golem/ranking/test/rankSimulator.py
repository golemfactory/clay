import sys
import os
import random
from copy import copy

sys.path.append( os.environ.get( 'GOLEM' ) )

from golem.ranking.simpleRank import SimpleRank

class RankSimulator:
    def __init__( self ):
        self.nodes = {}
        self.nodesCnt = 0
        self.optPeers = 3
        self.trustThreshold = 0.2
        self.nodesForTask = 2
        self.goodTaskReward = 0.1
        self.badTaskPunishment = 0.2
        self.paymentReward = 0.2
        self.badPaymentPunishment = 0.3

    def addNode( self, goodNode = True ):
        self.nodesCnt += 1
        self.nodes['node{}'.format( self.nodesCnt)] = {'ranking': SimpleRank(), 'peers': set(), 'good': goodNode }

    def fullAddNode( self, goodNode = True ):
        self.addNode( goodNode )
        self.connectNode( "node{}".format( self.nodesCnt ) )
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
        for n in random.sample( countingNodes, self.nodesForTask ):
            if n != node:
                if self.askForNode( n, node ) and self.askForNode( node, n ):
                    self.countTask( n, node )

    def countTask(self, cntNode, forNode ):
        if cntNode not in self.nodes:
            print "Wrong node {}".format( cntNode )
        if forNode not in self.nodes:
            print "Wrong node {}".format( forNode )

        if self.nodes[cntNode]['good']:
            self.nodes[forNode]['ranking'].setNodeRank( cntNode, self.nodes[ forNode]['ranking'].getNodeRank( cntNode ) + self.goodTaskReward )
            if self.nodes[forNode]['good']:
                self.nodes[cntNode]['ranking'].setNodeRank( forNode, self.nodes[ cntNode ]['ranking'].getNodeRank( forNode ) + self.paymentReward )
            else:
                self.nodes[cntNode]['ranking'].setNodeRank( forNode, self.nodes[ cntNode ]['ranking'].getNodeRank( forNode ) - self.badPaymentPunishment )
        else:
            self.nodes[forNode]['ranking'].setNodeRank( cntNode, self.nodes[ forNode]['ranking'].getNodeRank( cntNode ) - self.badTaskPunishment )
            self.nodes[cntNode]['ranking'].setNodeRank( forNode, self.nodes[ cntNode ]['ranking'].getNodeRank( forNode ) - self.badPaymentPunishment )


    def askForNode( self, node, forNode ):
        if node not in self.nodes:
            print "Wrong node {}".format( node )
        if forNode not in self.nodes:
            print "Wrong node {}".format( forNode )

        otherRank = {}
        for peer in self.nodes[node]['peers']:
            otherRank[peer] = self.nodes[peer]['ranking'].getNodeRank( forNode )

        self.nodes[node]['ranking'].changeNodeRank( forNode, otherRank )
        if self.nodes[node]['ranking'].getNodeRank( forNode ) > self.trustThreshold:
            return True
        else:
            if forNode in self.nodes[node]['peers']:
                self.nodes[node]['peers'].remove( forNode )
            return False



def main():
    rs = RankSimulator()
    for i in range(0, 5):
        rs.fullAddNode( goodNode = False )
    for i in range(0, 25):
        rs.fullAddNode( goodNode = True )

    rs.printState()
    for i in range(0, 2000):
        rs.startTask( random.sample( rs.nodes.keys(), 1)[0] )
    rs.printState()


main()

