import sys
import os
import random


sys.path.append( os.environ.get( 'GOLEM' ) )

from golem.ranking.eigenTrustRank import EigenTrustRank
from rankSimulator import RankSimulator

class EigenTrustNodeRank:
    def __init__( self ):
        self.computing = EigenTrustRank()
        self.delegating = EigenTrustRank()

    def setSeedRank( self, seedNode ):
        pass

    def __str__( self ):
        return "Computing: {}, ".format( self.computing ) +"Delegating: {}, ".format( self.delegating )



class EigenTrustSimulator( RankSimulator ):
    def __init__( self, optPeers = 3, trustThreshold = -1.0):
        RankSimulator.__init__( self, EigenTrustNodeRank, optPeers )
        self.trustThreshold = trustThreshold

    def goodCounting( self, cntNode, dntNode ):
        self.nodes[ dntNode ]['ranking'].computing.incNodePositive( cntNode )

    def badCounting( self, cntNode, dntNode ):
        self.nodes[ dntNode ]['ranking'].computing.incNodeNegative( cntNode )
        self.nodes[ cntNode ]['ranking'].delegating.incNodeNegative( dntNode )

    def goodPayment( self, cntNode, dntNode ):
        self.nodes[ cntNode ]['ranking'].delegating.incNodePositive( dntNode )

    def noPayment( self, cntNode, dntNode ):
        self.nodes[ cntNode ]['ranking'].delegating.incNodeNegative( dntNode )


    def askForNodeComputing( self, dntNode, cntNode ):
        if cntNode not in self.nodes:
            print "Wrong node {}".format( cntNode )
        if dntNode not in self.nodes:
            print "Wrong node {}".format( dntNode )

        otherRanks = {}
        for peer in self.nodes[ dntNode ]['peers']:
            otherRanks[peer] = self.nodes[peer]['ranking'].computing.getNodeTrust( cntNode )

        test = self.nodes[dntNode]['ranking'].computing.getGlobalTrust( cntNode, otherRanks )
        print "DNT NODE {}, CNT NODE{} GLOBAL {}".format( dntNode, cntNode, test )
        if test > self.trustThreshold:
            return True
        else:
            return False

    def askForNodeDelegating( self, cntNode, dntNode ):
        if cntNode not in self.nodes:
            print "Wrong node {}".format( cntNode )
        if dntNode not in self.nodes:
            print "Wrong node {}".format( dntNode )

        otherRanks = {}
        for peer in self.nodes[ cntNode ]['peers']:
            otherRanks[peer] = self.nodes[peer]['ranking'].delegating.getNodeTrust( dntNode )

        test = self.nodes[cntNode]['ranking'].delegating.getGlobalTrust( dntNode, otherRanks )
        print "CNT NODE {}, DNT NODE{} GLOBAL {}".format( cntNode, dntNode, test )
        if test > self.trustThreshold:
            return True
        else:
            return False



def main():
    rs = EigenTrustSimulator()
    for i in range(0, 1):
        rs.fullAddNode( goodNode = False )
    for i in range(0, 10):
        rs.fullAddNode( goodNode = True )

    rs.printState()
    print "################"
    for i in range(0, 100):
        rs.startTask( random.sample( rs.nodes.keys(), 1)[0] )
    rs.printState()



if __name__ == "__main__":
    main()
