class SimpleRank:
    def __init__( self ):
        self.ranking = {}
        self.basicRank = 0.5
        self.maxRank = 1.0
        self.minRank = 0.0
        self.seedRank = 1.0

    def __str__( self ):
        return "Ranking {}".format( self.ranking )

    def getNodeRank( self, nodeId ):
        if nodeId in self.ranking:
            return self.ranking[ nodeId ]
        else:
            return None

    def setNodeRank( self, nodeId, rank ):
        if rank > self.maxRank:
            rank = self.maxRank
        if rank < self.minRank:
            rank = self.minRank
        self.ranking[ nodeId ] = rank

    def setBasicNodeRank( self, nodeId ):
        if nodeId not in self.ranking:
            self.ranking[ nodeId ] = self.basicRank

    def setSeedRank( self, nodeId ):
        self.ranking[ nodeId ] = self.seedRank

    def changeNodeRank( self, nodeId, otherRanks ):
        weightSum = 0.0
        rankSum = 0.0
        for nId, rank in otherRanks.iteritems():
            if rank is not None:
                if nId in self.ranking:
                    rankSum += self.ranking[ nId ] * rank
                    weightSum += self.ranking[ nId ]
                else:
                    rankSum += self.basicRank * rank
                    weightSum += self.basicRank

        if nodeId in self.ranking:
            if weightSum == 0:
                weightSum = 1.0
                rankSum += self.ranking[ nodeId ]
            else:
                rankSum += self.ranking[ nodeId ] * weightSum
                weightSum *= 2
        else:
            rankSum += self.basicRank
            weightSum += 1.0

        self.setNodeRank( nodeId, rankSum / weightSum )

