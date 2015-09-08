class EigenTrustRank:

    def __init__(self):
        self.positive = {}
        self.negative = {}

    def __str__(self):
        return "Positive: {}, Negative: {}, ".format(self.positive, self.negative)

    def getNodeTrust(self, node_id, normalize = True):
        p = 0
        n = 0
        if node_id in self.positive:
            p = self.positive[ node_id ]
        if node_id in self.negative:
            n = self.negative[ node_id ]

        if not normalize:
            return float(p - n)
        else:
            maxTrust = self.maxTrust()
            if maxTrust == 0.0:
                return 0.0
            return float(max(p - n, 0.0) / maxTrust)

    def maxTrust(self):
        nodes = set(self.positive.keys() + self.negative.keys())
        trusts = [ self.getNodeTrust(node, normalize = False) for node in nodes ]
        if len(trusts) == 0:
            return 0
        return float(max(trusts))

    def getNodePostive(self, node_id):
        if node_id in self.positive:
            return self.positive[ node_id ]
        else:
            return None

    def getNodeNegative(self, node_id):
        if node_id in self.negative:
            return self.negative[ node_id ]
        else:
            return None

    def setNodePositive(self, node_id, value):
        self.positive[ node_id ] = value

    def incNodePositive(self, node_id):
        val = self.getNodePostive(node_id)
        if val is not None:
            self.setNodePositive(node_id, val + 1)
        else:
            self.setNodePositive(node_id,  1)

    def incNodeNegative(self, node_id):
        val = self.getNodeNegative(node_id)
        if val is not None:
            self.setNodeNegative(node_id, val + 1)
        else:
            self.setNodeNegative(node_id,  1)


    def setNodeNegative(self, node_id, value):
        self.negative[ node_id ] = value

    def getGlobalTrust(self, node_id, otherTrusts):

        globalTrust = 0
        for node in otherTrusts.keys():
            globalTrust += self.getNodeTrust(node) * otherTrusts[ node ]

        return globalTrust
