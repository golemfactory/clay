from numpy import zeros, hstack, vstack, matrix
import math
from random import randint, sample


class GossipTrustTest:
    def __init__(self, epsilon=0.1, delta=0.1, goosip_score_max_steps=10000, aggregation_max_steps=4):
        self.local_ranking = None
        self.local_ranking_mapping = {}
        self.lastGlobalRanking = None
        self.global_ranking = None
        self.epsilon = epsilon
        self.delta = delta
        self.gossip_score_steps = 0
        self.goosip_score_max_steps = goosip_score_max_steps
        self.aggregationSteps = 0
        self.aggregation_max_steps = aggregation_max_steps
        self.globalReputationCycles = 0
        # self.outerSend = outerSender
        self.weighted_scores = None
        self.consensus_factors = None
        self.collectedPairs = None
        self.previous_score = None
        self.infValue = 10.0

    def add_node(self, node_id):
        if node_id in self.local_ranking_mapping:
            return
        else:
            n = len(self.local_ranking_mapping)
            self.local_ranking_mapping[node_id] = n
            n += 1
            if n == 1:
                self.local_ranking = matrix([1.])
                return
            self.local_ranking = hstack([vstack([self.local_ranking, zeros([1, n - 1])]), zeros([n, 1])])

    def update_reputation(self, node_id):
        pass

    def start_new_cycle(self):
        self.gossip_score_steps = 0
        n = len(self.local_ranking_mapping)
        self.global_ranking = matrix([1.0 / float(n)] * len(self.local_ranking_mapping)).transpose()

    def aggregation_cycle(self):
        self.globalReputationCycles += 1
        n = len(self.local_ranking_mapping)
        norm_matrix = matrix([n, n])
        for i in range(0, n):
            row_sum = sum(self.local_ranking[i])
            for j in range(0, n):
                norm_matrix[i][j] = self.local_ranking[i][j] / row_sum

        self.lastGlobalRanking = self.global_ranking
        self.global_ranking = norm_matrix.transpose() * self.global_ranking

    def get_weighted_score(self, node_id):
        i = self.local_ranking_mapping[node_id]
        return self.global_ranking[i] * self.local_ranking[i]

    def do_aggregation(self):
        self.start_new_cycle()
        while True:
            self.aggregation_cycle()
            if self.stop_aggregation():
                break

    def stop_aggregation(self):
        max_val = max(self.absmax(self.lastGlobalRanking), self.absmax(self.global_ranking))
        minus_max_val = max(self.absmax(self.global_ranking - self.lastGlobalRanking))
        return float(minus_max_val) / float(max_val) <= self.delta

    def absmax(self, m):
        return max(m.max(), m.min(), key=abs)

    def start_gossip(self, node_id):
        if node_id not in self.local_ranking_mapping:
            self.add_node(node_id)

        j = self.local_ranking_mapping[node_id]
        n = len(self.local_ranking_mapping)
        self.weighted_scores = [None] * n
        self.consensus_factors = [None] * n
        self.collectedPairs = [None] * n
        self.previous_score = [None] * n
        for i in range(0, n):
            self.weighted_scores[i] = self.local_ranking[i, j] * self.global_ranking[i, 0]
            if i == j:
                self.consensus_factors[i] = 1.0
            else:
                self.consensus_factors[i] = 0.0
            self.previous_score[i] = self.infValue
            self.collectedPairs[i] = [[self.weighted_scores[i], self.consensus_factors[i]]]
        self.gossip_score_steps = 0

    def do_gossip(self, node_id):
        self.start_gossip(node_id)

        while True:
            self.gossip_step()
            if self.stop_gossip():
                break

    def stop_gossip(self):
        stop = 0
        if self.gossip_score_steps >= self.goosip_score_max_steps:
            return True
        for i in range(0, len(self.local_ranking_mapping)):
            if self.weighted_scores[i] == 0:
                new_score = 0.0
            elif self.consensus_factors[i] == 0:
                new_score = self.infValue
            else:
                new_score = float(self.weighted_scores[i]) / float(self.consensus_factors[i])
            print "ABS " + str(abs(new_score))
            print "EPSILON " + str(self.epsilon)
            if abs(new_score - self.previous_score[i]) <= self.epsilon:
                print "STOP + 1"
                stop += 1
            self.previous_score[i] = new_score
            print stop
        return stop == len(self.local_ranking_mapping)

    def gossip_step(self):

        self.gossip_score_steps += 1
        n = len(self.local_ranking_mapping)
        for i in range(0, n):
            self.weighted_scores[i] = 0.0
            self.consensus_factors[i] = 0.0
            for pair in self.collectedPairs[i]:
                self.weighted_scores[i] += pair[0]
                self.consensus_factors[i] += pair[1]
            self.collectedPairs[i] = []

        for i in range(0, n):
            self.collectedPairs[i].append([self.weighted_scores[i] / 2.0, self.consensus_factors[i] / 2.0])
            r = randint(0, n - 1)
            if n > 1:
                while r == i:
                    r = randint(0, n - 1)
            self.collectedPairs[r].append([self.weighted_scores[i] / 2.0, self.consensus_factors[i] / 2.0])


class GossipPositiveNegativeTrustRank:
    def __init__(self, pos_trust_val=1.0, neg_trust_val=2.0, min_sum_val=50):
        self.node_id = None
        self.positive = GossipTrustRank(self_value=1.0)
        self.negative = GossipTrustRank(self_value=0.0)
        self.pos_trust_val = pos_trust_val
        self.neg_trust_val = neg_trust_val
        self.min_sum_val = min_sum_val
        self.glob_vec = {}
        self.gossip_num = 0

    def __str__(self):
        return "[Positive: {}, Negative: {}]".format(self.positive, self.negative)

    def inc_node_positive(self, node_id):
        self.positive.inc_node_rank(node_id)

    def inc_node_negative(self, node_id):
        self.negative.inc_node_rank(node_id)

    def set_node_id(self, node_id):
        self.node_id = node_id
        self.positive.set_node_id(node_id)
        self.negative.set_node_id(node_id)

    def get_node_positive(self, node_id):
        return self.positive.get_node_rank(node_id)

    def get_node_negative(self, node_id):
        return self.negative.get_node_rank(node_id)

    def set_node_positive(self, node_id, value):
        self.positive.set_node_rank(node_id, value)

    def set_node_negative(self, node_id, value):
        self.negative.set_node_rank(node_id, value)

    def get_node_trust(self, node_id):
        pos = self.positive.get_node_rank(node_id)
        if pos is None:
            pos = 0.0
        neg = self.negative.get_node_rank(node_id)
        if neg is None:
            neg = 0.0
        val = (self.pos_trust_val * pos - self.neg_trust_val * neg)
        sum_val = max(self.min_sum_val, pos + neg)
        return float(val) / float(sum_val)

    def start_aggregation(self):
        self.positive.start_aggregation()
        self.negative.start_aggregation()

    def stop_aggregation(self, fin_pos, fin_neg):
        stop_pos = fin_pos
        stop_neg = fin_neg
        if not stop_pos:
            stop_pos = self.positive.stop_aggregation()
        if not stop_neg:
            stop_neg = self.negative.stop_aggregation()
        return [stop_pos, stop_neg]

    def stop_gossip(self, fin_pos, fin_neg):
        stop_pos = fin_pos
        stop_neg = fin_neg
        if not stop_pos:
            stop_pos = self.positive.stop_gossip()
        if not stop_neg:
            stop_neg = self.negative.stop_gossip()
        return [stop_pos, stop_neg]

    def prep_aggregation(self, fin_pos, fin_neg):
        if not fin_pos:
            self.positive.prep_aggregation()
        if not fin_neg:
            self.negative.prep_aggregation()

    def do_gossip(self, fin_pos, fin_neg):
        gossip = [None, None]
        if not fin_pos:
            gossip[0] = self.positive.do_gossip()
        if not fin_neg:
            gossip[1] = self.negative.do_gossip()
        return gossip


class GossipTrustRank:
    def __init__(self, delta=0.1, epsilon=0.1, self_value=1.0):
        self.node_id = None
        self.ranking = {}
        self.weighted_score = {}
        self.glob_vec = {}
        self.prev_vec = {}
        self.prev_gossip_vec = {}
        self.collected_vecs = []
        self.delta = delta
        self.epsilon = epsilon
        self.inf = float("inf")
        self.print_data = False
        self.self_value = self_value

    def __str__(self):
        return "[Ranking: {}, weighted_score: {}, self.glob_vec: {}] ".format(self.ranking,
                                                                              self.weighted_score,
                                                                              self.glob_vec)

    def set_node_id(self, node_id):
        self.node_id = node_id

    def inc_node_rank(self, node_id):
        val = self.get_node_rank(node_id)
        if val is not None:
            self.set_node_rank(node_id, val + 1)
        else:
            self.set_node_rank(node_id, 1)

    def get_node_rank(self, node_id):
        if node_id in self.ranking:
            return self.ranking[node_id]
        else:
            return None

    def get_node_negative(self, node_id):
        if node_id in self.negative:
            return self.negative[node_id]
        else:
            return None

    def set_node_rank(self, node_id, value):
        self.ranking[node_id] = value

    def start_aggregation(self):
        print "start_aggregation"
        self.weighted_score = {}
        norm = sum(self.ranking.values())
        n = len(self.ranking)
        for node_id in self.ranking:
            loc_trust_value = float(self.ranking[node_id]) / float(norm)
            self.weighted_score[node_id] = loc_trust_value / float(n + 1)

        if n == 0:
            self.weighted_score[self.node_id] = self.self_value
        else:
            self.weighted_score[self.node_id] = 1.0 / float(n + 1)

        self.update_glob_vec()

        self.collected_vecs = [self.glob_vec]
        self.prev_vec = {}
        self.prev_gossip_vec = {}

    def prep_aggregation(self):
        self.prev_vec = self.glob_vec
        norm = sum(self.ranking.values())
        for node_id in self.ranking:
            loc_trust_value = float(self.ranking[node_id]) / float(norm)
            glob_vec_trust_value = self.count_div(self.glob_vec[node_id][0], self.glob_vec[node_id][1])
            self.weighted_score[node_id] = loc_trust_value * glob_vec_trust_value
        self.update_glob_vec()

    def count_div(self, a, b):
        if a == 0.0:
            return 0.0
        if b == 0.0:
            return self.inf
        return float(a) / float(b)

    def stop_aggregation(self):
        return self.compare_vec(self.glob_vec, self.prev_vec) <= self.delta

    def stop_gossip(self):
        return self.compare_vec(self.glob_vec, self.prev_gossip_vec) <= self.epsilon

    def compare_vec(self, vec1, vec2):
        #        print "COMPARE VEC {}, {}".format(vec1, vec2)
        nodes1 = set(vec1.keys())
        nodes2 = set(vec2.keys())
        if set(nodes1) != set(nodes2):
            return self.inf

        val = 0
        for node in nodes1:
            v = self.count_div(vec1[node][0], vec1[node][1]) - self.count_div(vec2[node][0], vec2[node][1])
            val += v * v
        return math.sqrt(val)

    def update_glob_vec(self):
        for node_id, node in self.weighted_score.iteritems():
            if node_id == self.node_id:
                self.glob_vec[node_id] = [node, 1.0]
            else:
                self.glob_vec[node_id] = [node, 0.0]

    def do_gossip(self):
        if self.print_data:
            print self.prev_gossip_vec
        self.prev_gossip_vec = self.glob_vec
        if len(self.collected_vecs) > 0:
            self.glob_vec = {}
        for vec in self.collected_vecs:
            for node_id, val in vec.iteritems():
                if node_id not in self.glob_vec:
                    self.glob_vec[node_id] = val
                else:
                    self.glob_vec[node_id][0] += val[0]
                    self.glob_vec[node_id][1] += val[1]

        self.collected_vecs = []

        vec_to_send = {}
        for node_id, val in self.glob_vec.iteritems():
            vec_to_send[node_id] = [val[0] / 2.0, val[1] / 2.0]

        return [vec_to_send, self.node_id]

    def hear_gossip(self, gossip):
        if self.print_data:
            print "NODE {} hear gossip {}".format(self.node_id, gossip)
        self.collected_vecs.append(gossip)

    def get_node_trust(self, node_id):
        if node_id in self.glob_vec:
            return self.count_div(self.glob_vec[0], self.glob_vec[1])
        else:
            return 0.0
