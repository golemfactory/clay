class SimpleRank:
    def __init__(self):
        self.ranking = {}
        self.basic_rank = 0.5
        self.maxRank = 1.0
        self.minRank = 0.0
        self.seed_rank = 1.0

    def __str__(self):
        return "Ranking {}".format(self.ranking)

    def get_node_rank(self, node_id):
        if node_id in self.ranking:
            return self.ranking[node_id]
        else:
            return None

    def set_node_rank(self, node_id, rank):
        if rank > self.maxRank:
            rank = self.maxRank
        if rank < self.minRank:
            rank = self.minRank
        self.ranking[node_id] = rank

    def set_basic_node_rank(self, node_id):
        if node_id not in self.ranking:
            self.ranking[node_id] = self.basic_rank

    def set_seed_rank(self, node_id):
        self.ranking[node_id] = self.seed_rank

    def global_node_rank(self, node_id, other_ranks):
        weight_sum = 0.0
        rank_sum = 0.0
        for n_id, rank in other_ranks.iteritems():
            if rank is not None:
                if n_id in self.ranking:
                    rank_sum += self.ranking[n_id] * rank
                    weight_sum += self.ranking[n_id]
                else:
                    rank_sum += self.basic_rank * rank
                    weight_sum += self.basic_rank

        if node_id in self.ranking:
            if weight_sum == 0:
                weight_sum = 1.0
                rank_sum += self.ranking[node_id]
            else:
                rank_sum += self.ranking[node_id] * weight_sum
                weight_sum *= 2
        else:
            rank_sum += self.basic_rank
            weight_sum += 1.0

        return rank_sum / weight_sum
