class SimpleRank:
    def __init__(self):
        self.ranking = {}
        self.basicRank = 0.5
        self.maxRank = 1.0
        self.minRank = 0.0
        self.seedRank = 1.0

    def __str__(self):
        return "Ranking {}".format(self.ranking)

    def getNodeRank(self, node_id):
        if node_id in self.ranking:
            return self.ranking[ node_id ]
        else:
            return None

    def setNodeRank(self, node_id, rank):
        if rank > self.maxRank:
            rank = self.maxRank
        if rank < self.minRank:
            rank = self.minRank
        self.ranking[ node_id ] = rank

    def setBasicNodeRank(self, node_id):
        if node_id not in self.ranking:
            self.ranking[ node_id ] = self.basicRank

    def setSeedRank(self, node_id):
        self.ranking[ node_id ] = self.seedRank

    def globalNodeRank(self, node_id, otherRanks):
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

        if node_id in self.ranking:
            if weightSum == 0:
                weightSum = 1.0
                rankSum += self.ranking[ node_id ]
            else:
                rankSum += self.ranking[ node_id ] * weightSum
                weightSum *= 2
        else:
            rankSum += self.basicRank
            weightSum += 1.0

        return rankSum / weightSum


