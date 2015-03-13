
import random

from rankSimulator import RankSimulator
from diffGossipTrustRank import DiffGossipTrustRank

class DiffGossipTrustNodeRank:
    def __init__( self ):
        self.computing = DiffGossipTrustRank()
        self.delegating = DiffGossipTrustRank()
        self.nodeId = None

    def setNodeId( self, nodeId ):
        self.nodeId = nodeId
        self.computing.setNodeId( nodeId )
        self.delegating.setNodeId( nodeId )
        self.computingFinished = False
        self.delegatingFinished = False

    def setSeedRank( self, seedNode ):
        pass

    def __str__( self ):
        return "Computing: {}, ".format( self.computing ) +"Delegating: {} ".format( self.delegating )

    def startDiffGossip( self , k ):
        gossip = [ None, None ]
        self.computing.startDiffGossip( k )
        self.delegating.startDiffGossip( k )

    def doGossip( self, finished ):
        gossips = [ None, None ]
        if not finished[0]:
            gossips[0] = self.computing.doGossip()
        if not finished[1]:
            gossips[1] = self.delegating.doGossip()
        return gossips

    def stopGossip(self, finished ):
        if not finished[0]:
            self.computing.stopGossip()
        if not finished[1]:
            self.delegating.stopGossip()



class DifferentialGossipTrustSimulator( RankSimulator ):
    def __init__( self, computingTrustThreshold = -0.9, delegatingTrustThreshold = -0.9, gossipMaxSteps = 100 ):
        RankSimulator.__init__( self, DiffGossipTrustNodeRank )
        self.delegatingTrustThreshold = delegatingTrustThreshold
        self.computingTrustThreshold = computingTrustThreshold

        self.gossipMaxSteps = gossipMaxSteps
        self.finished = [ False, False ]
        self.gossipStep = 0


    def addNode( self, goodNode = True ):
        RankSimulator.addNode( self, goodNode )
        self.ranking[self.lastNode].setNodeId( self.lastNode )

    def goodCounting( self, cntNode, dntNode ):
        self.ranking[ dntNode ].computing.incNodePositive( cntNode )

    def badCounting( self, cntNode, dntNode ):
        self.ranking[ dntNode ].computing.incNodeNegative( cntNode )
        self.ranking[ cntNode ].delegating.incNodeNegative( dntNode )

    def goodPayment( self, cntNode, dntNode ):
        self.ranking[ cntNode ].delegating.incNodePositive( dntNode )


    def noPayment( self, cntNode, dntNode ):
        self.ranking[ cntNode ].delegating.incNodeNegative( dntNode )

    def askForNodeComputing( self, cntNode, dntNode ):
        if self.ranking[ dntNode ].computing.getNodePositive( cntNode ) is None and self.ranking[ dntNode ].computing.getNodeNegative( cntNode ) is None:
            opinion = self.getGlobalComputingOpinion( cntNode, dntNode )
        else:
            opinion =  self.selfComputingOpinion( cntNode,dntNode )
        return opinion > self.computingTrustThreshold

    def getGlobalComputingOpinion( self, cntNode, dntNode ):
        opinion = self.ranking[ dntNode ].computing.getGlobalVal( cntNode )
        if opinion is None:
            opinion = 0.0
        return opinion

    def getGlobalDelegatingOpinion( self, cntNode, dntNode ):
        opinion = self.ranking[ dntNode ].computing.getGlobalVal( cntNode )
        if opinion is None:
            opinion = 0.0
        return opinion

    def selfComputingOpinion( self, cntNode, dntNode ):
        return self.ranking[ dntNode ].computing.getNodeTrust( cntNode ) > self.computingTrustThreshold

    def askForNodeDelegating( self, cntNode, dntNode ):
        if self.ranking[ cntNode ].delegating.getNodePositive( cntNode ) is None and self.ranking[cntNode].delegating.getNodeNegative( dntNode ) is None:
            opinion = self.getGlobalDelegatingOpinion( dntNode, cntNode )
        else:
            opinion = self.selfDelegatingOpinion( cntNode, dntNode )
        return opinion > self.delegatingTrustThreshold

    def selfDelegatingOpinion(self, cntNode, dntNode ):
        return self.ranking[ cntNode ].delegating.getNodeTrust( dntNode )

    def getNeighboursOpinion( self, node, forNode, computing ):
        opinions = {}
        for n in self.network.nodes[ node ]:
            if computing:
                trust = self.ranking[ n ].computing.getNodeTrust( forNode )
            else:
                trust = self.ranking[ n ].delegating.getNodeTrust( forNode )
            opinions[ n ] = trust

        return opinions

    def listenToOpinions(self, node, forNode, opinions, threshold ):
        val = 0
        cnt = 0
        for nodeId, opinion in opinions.iteritems():
            val += opinion
            cnt += 1
        if cnt > 0:
            neighOpinion = float( val ) / float( cnt )
        else:
            neighOpinion = 0.0
        return neighOpinion > threshold

    def syncRanking( self ):
        k = self.countGossipNumVec()
        self.startGossip( k )
        while True:
            self.doGossip( )
            if self.gossipStep > 0 and self.stopGossip():
                break
            self.gossipStep += 1
            if self.gossipStep >= self.gossipMaxSteps:
                break
        print "GOSSIP STEP {}".format( self.gossipStep )
        self.gossipStep = 0

    def startGossip(self, k):
        self.gossipStep = 0
        self.finished = [ False, False ]
        for rank in self.ranking.values():
            rank.startDiffGossip( k[ rank.nodeId ] )


    def doGossip( self ):
        gossips = []
        for rank in self.ranking.values():
            gossips.append( rank.doGossip( self.finished ) )

        self.sendGossips( gossips )

    def countGossipNumVec( self ):
        nodes = self.ranking.keys()
        k = {}
        for node in nodes:
            degree = self.network.getDegree( node )
            neighboursDegree = self.network.getAvgNeighboursDegree( node )
            if neighboursDegree == 0.0:
                k[ node ] = 0
            else:
                k[ node ] = max( int( round( float( degree ) / float( neighboursDegree ) )), 1 )

        print k
        return k

    def sendGossips( self, gossips ):
        for gossip in gossips:
            if gossip[0] is not None and len( gossip[0] ) > 0:
                gossipVec, node1 = gossip[0]
                print "gossipVec {}, node1 {}".format( gossipVec, node1 )
                self.ranking[node1].computing.hearGossip( gossipVec )
                k = self.ranking[node1].computing.gossipNum
                nodes = self.getRandomNeighbours( node1, k )
                for node in nodes:
                    self.ranking[node].computing.hearGossip( gossipVec )
            if gossip[1] is not None and len( gossip[1] ) > 0:
                gossipVec, node1 = gossip[1]
                self.ranking[node1].delegating.hearGossip( gossipVec )
                k = self.ranking[node1].delegating.gossipNum
                nodes = self.getRandomNeighbours( node1, k )
                for node in nodes:
                    self.ranking[node].computing.hearGossip( gossipVec )

    def getRandomNeighbours(self, nodeId, k ):
        return random.sample( self.network.nodes[nodeId], k)


    def stopGossip( self ):
        nodes = self.ranking.keys()
        for node in nodes:
            self.ranking[node].stopGossip( self.finished )
        stoppedCom = 0
        stoppedDel = 0
        print self.finished
        for node in nodes:
            if not self.finished[0]:
                neighboursStopped = True
                if self.ranking[node].computing.isStopped():

                    for neigh in self.network.nodes[ node ]:
                        if not self.ranking[neigh].computing.isStopped():
                            neighboursStopped = False
                    if neighboursStopped:
                        self.ranking[node].computing.neighStopped()
                        stoppedCom += 1
            if not self.finished[1]:
                neighboursStopped = True
                if self.ranking[node].delegating.isStopped():
                    for neigh in self.network.nodes[ node ]:
                        if not self.ranking[ neigh ].delegating.isStopped():
                            neighboursStopped = False
                    if neighboursStopped:
                        self.ranking[node].delegating.neighStopped()
                        stoppedDel +=1
        print "STOPPED {} {}".format( stoppedCom, stoppedDel )
        if stoppedCom == len( nodes ):
            self.finished[0] = True
        if stoppedDel == len( nodes ):
            self.finished[1] = True

        return self.finished[0] and self.finished[1]





def main():
    rs = DifferentialGossipTrustSimulator()

    for i in range(0, 1):
        rs.fullAddNode( goodNode = False )
    for i in range(0, 5):
        rs.fullAddNode( goodNode = True )
    rs.printState()
    rs.syncNetwork()


    print "################"
    for i in range(0, 200):
        rs.syncNetwork()
        rs.startTask( random.sample( rs.ranking.keys(), 1)[0] )

        rs.syncRanking()
    rs.printState()


if __name__ == "__main__":
    main()
