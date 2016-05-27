import math
import random


class LocalRank:
    def __init__(self):
        self.ranking = {}

    def get_node_rank(self, node_id):
        if node_id in self.ranking:
            return self.ranking[node_id]
        else:
            return None

    def set_node_rank(self, node_id, value):
        self.ranking[node_id] = value

    def inc_node_rank(self, node_id):
        val = self.get_node_rank(node_id)
        if val is not None:
            self.set_node_rank(node_id, val + 1)
        else:
            self.set_node_rank(node_id, 1)


def div_trust(a, b):
    if a == 0.0:
        return 0.0
    if b == 0.0:
        return float('inf')
    return float(a) / float(b)


def compare_vec(vec1, vec2):
    print "COMPARE {} {}".format(vec1, vec2)
    val = 0
    for node in vec2.keys():
        if node not in vec1.keys():
            return float("inf")
        v = vec1[node] - vec2[node]
        val += v * v
    return math.sqrt(val)


class DiffGossipTrustRank:
    def __init__(self, pos_trust_val=1.0, neg_trust_val=2.0, min_sum_val=50, epsilon=0.01):
        self.node_id = None
        self.positive = LocalRank()
        self.negative = LocalRank()

        self.pos_trust_val = pos_trust_val
        self.neg_trust_val = neg_trust_val
        self.min_sum_val = min_sum_val
        self.epsilon = epsilon

        self.gossip_num = 0
        self.glob_vec = {}
        self.working_vec = {}
        self.collected_vecs = []
        self.global_stop = False
        self.stop = False

    def __str__(self):
        return "glob_vec: {}".format(self.glob_vec)

    def inc_node_positive(self, node_id):
        self.positive.inc_node_rank(node_id)

    def inc_node_negative(self, node_id):
        self.negative.inc_node_rank(node_id)

    def set_node_id(self, node_id):
        self.node_id = node_id

    def get_node_positive(self, node_id):
        return self.positive.get_node_rank(node_id)

    def get_node_negative(self, node_id):
        return self.negative.get_node_rank(node_id)

    def set_node_positive(self, node_id, value):
        self.positive.set_node_rank(node_id, value)

    def set_node_negative(self, node_id, value):
        self.negative.set_node_rank(node_id, value)

    def is_stopped(self):
        return self.stop

    def get_node_trust(self, node_id):
        pos = self.positive.get_node_rank(node_id)
        if pos is None:
            pos = 0.0
        neg = self.negative.get_node_rank(node_id)
        if neg is None:
            neg = 0.0
        val = (self.pos_trust_val * pos - self.neg_trust_val * neg)
        sum_val = max(self.min_sum_val, pos + neg)
        return max(min(float(val) / float(sum_val), 1.0), -1.0)

    def start_diff_gossip(self, k):
        self.gossip_num = k
        self.working_vec = {}
        self.stop = False
        self.global_stop = False
        known_nodes = set(self.positive.ranking.keys() + self.negative.ranking.keys())
        for node in known_nodes:
            self.working_vec[node] = [self.get_node_trust(node), 1.0, 0.0]
        for node in self.glob_vec:
            if node not in known_nodes:
                self.working_vec[node] = [0.0, 0.0, 0.0]
        if len(self.working_vec) > 0:
            rand_node = random.sample(self.working_vec.keys(), 1)[0]
            self.working_vec[rand_node][1] = 1.0
        for node, val in self.working_vec.iteritems():
            self.glob_vec[node] = div_trust(val[0], val[1])
        self.collected_vecs = [self.working_vec]

    def do_gossip(self):

        if self.global_stop:
            return []
        self.working_vec = {}
        for vec in self.collected_vecs:
            for node_id, val in vec.iteritems():
                if node_id not in self.working_vec:
                    self.working_vec[node_id] = val
                else:
                    self.working_vec[node_id][0] += val[0]
                    self.working_vec[node_id][1] += val[1]
                    self.working_vec[node_id][2] += val[2]

        self.collected_vecs = []

        vec_to_send = {}
        for node_id, val in self.working_vec.iteritems():
            vec_to_send[node_id] = [val[0] / self.gossip_num, val[1] / self.gossip_num, val[2] / self.gossip_num]

        return [vec_to_send, self.node_id]

    def hear_gossip(self, gossip):
        self.collected_vecs.append(gossip)

    def get_global_val(self, node_id):
        if node_id in self.glob_vec:
            return self.glob_vec[node_id]
        return None

    def stop_gossip(self):
        if self.stop:
            return True
        else:
            new_glob_vec = {}
            for node, val in self.working_vec.iteritems():
                new_glob_vec[node] = div_trust(val[0], val[1])
            if compare_vec(self.glob_vec, new_glob_vec) < self.epsilon:
                self.stop = True
            for node, val in new_glob_vec.iteritems():
                self.glob_vec[node] = val
            return self.stop

    def neigh_stopped(self):
        self.global_stop = True
