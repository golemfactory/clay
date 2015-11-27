class EigenTrustRank:

    def __init__(self):
        self.positive = {}
        self.negative = {}

    def __str__(self):
        return "Positive: {}, Negative: {}, ".format(self.positive, self.negative)

    def get_node_trust(self, node_id, normalize=True):
        p = 0
        n = 0
        if node_id in self.positive:
            p = self.positive[node_id]
        if node_id in self.negative:
            n = self.negative[node_id]

        if not normalize:
            return float(p - n)
        else:
            max_trust = self.max_trust()
            if max_trust == 0.0:
                return 0.0
            return float(max(p - n, 0.0) / max_trust)

    def max_trust(self):
        nodes = set(self.positive.keys() + self.negative.keys())
        trusts = [self.get_node_trust(node, normalize=False) for node in nodes]
        if len(trusts) == 0:
            return 0
        return float(max(trusts))

    def get_node_positive(self, node_id):
        if node_id in self.positive:
            return self.positive[node_id]
        else:
            return None

    def get_node_negative(self, node_id):
        if node_id in self.negative:
            return self.negative[node_id]
        else:
            return None

    def set_node_positive(self, node_id, value):
        self.positive[node_id] = value

    def inc_node_positive(self, node_id):
        val = self.get_node_positive(node_id)
        if val is not None:
            self.set_node_positive(node_id, val + 1)
        else:
            self.set_node_positive(node_id,  1)

    def inc_node_negative(self, node_id):
        val = self.get_node_negative(node_id)
        if val is not None:
            self.set_node_negative(node_id, val + 1)
        else:
            self.set_node_negative(node_id,  1)

    def set_node_negative(self, node_id, value):
        self.negative[node_id] = value

    def get_global_trust(self, node_id, other_trusts):

        global_trust = 0
        for node in other_trusts.keys():
            global_trust += self.get_node_trust(node) * other_trusts[node]

        return global_trust
