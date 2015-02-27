class EigenTrustRank:

    def __init__( self ):
        self.positive = {}
        self.negative = {}

    def __str__( self ):
        return "Positive: {}, Negative: {}, ".format( self.positive, self.negative )

    def getNodeTrust( self, nodeId, normalize = True ):
        p = 0
        n = 0
        if nodeId in self.positive:
            p = self.positive[ nodeId ]
        if nodeId in self.negative:
            n = self.negative[ nodeId ]

        if not normalize:
            return float( p - n )
        else:
            maxTrust = self.maxTrust()
            if maxTrust == 0.0:
                return 0.0
            return float( max( p - n, 0.0) / maxTrust )

    def maxTrust( self ):
        nodes = set( self.positive.keys() + self.negative.keys() )
        trusts = [ self.getNodeTrust( node, normalize = False ) for node in nodes ]
        if len( trusts ) == 0:
            return 0
        return float( max( trusts ) )

    def getNodePostive( self, nodeId ):
        if nodeId in self.positive:
            return self.positive[ nodeId ]
        else:
            return None

    def getNodeNegative( self, nodeId ):
        if nodeId in self.negative:
            return self.negative[ nodeId ]
        else:
            return None

    def setNodePositive( self, nodeId, value ):
        self.positive[ nodeId ] = value

    def incNodePositive( self, nodeId ):
        val = self.getNodePostive( nodeId )
        if val is not None:
            self.setNodePositive( nodeId, val + 1)
        else:
            self.setNodePositive(nodeId,  1)

    def incNodeNegative( self, nodeId ):
        val = self.getNodeNegative( nodeId )
        if val is not None:
            self.setNodeNegative( nodeId, val + 1)
        else:
            self.setNodeNegative(nodeId,  1)


    def setNodeNegative( self, nodeId, value ):
        self.negative[ nodeId ] = value

    def getGlobalTrust(self, nodeId, otherTrusts ):

        globalTrust = 0
        for node in otherTrusts.keys():
            globalTrust += self.getNodeTrust( node ) * otherTrusts[ node ]

        return globalTrust
