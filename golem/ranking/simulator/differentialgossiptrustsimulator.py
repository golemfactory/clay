import random
from ranksimulator import RankSimulator
from diffgossiptrustrank import DiffGossipTrustRank


class DiffGossipTrustNodeRank:
    def __init__(self):
        self.computing = DiffGossipTrustRank()
        self.delegating = DiffGossipTrustRank()
        self.node_id = None

    def set_node_id(self, node_id):
        self.node_id = node_id
        self.computing.set_node_id(node_id)
        self.delegating.set_node_id(node_id)
        self.computing_finished = False
        self.delegating_finished = False

    def set_seed_rank(self, seed_node):
        pass

    def __str__(self):
        return "Computing: {}, ".format(self.computing) + "Delegating: {} ".format(self.delegating)

    def start_diff_gossip(self, k):
        gossip = [None, None]
        self.computing.start_diff_gossip(k)
        self.delegating.start_diff_gossip(k)

    def do_gossip(self, finished):
        gossips = [None, None]
        if not finished[0]:
            gossips[0] = self.computing.do_gossip()
        if not finished[1]:
            gossips[1] = self.delegating.do_gossip()
        return gossips

    def stop_gossip(self, finished):
        if not finished[0]:
            self.computing.stop_gossip()
        if not finished[1]:
            self.delegating.stop_gossip()


class DifferentialGossipTrustSimulator(RankSimulator):
    def __init__(self, computing_trust_threshold=-0.9, delegating_trust_threshold=-0.9, gossip_max_steps=100):
        RankSimulator.__init__(self, DiffGossipTrustNodeRank)
        self.delegating_trust_threshold = delegating_trust_threshold
        self.computing_trust_threshold = computing_trust_threshold

        self.gossip_max_steps = gossip_max_steps
        self.finished = [False, False]
        self.gossip_step = 0

    def add_node(self, good_node=True):
        RankSimulator.add_node(self, good_node)
        self.ranking[self.last_node].set_node_id(self.last_node)

    def good_counting(self, cnt_node, dnt_node):
        self.ranking[dnt_node].computing.inc_node_positive(cnt_node)

    def bad_counting(self, cnt_node, dnt_node):
        self.ranking[dnt_node].computing.inc_node_negative(cnt_node)
        self.ranking[cnt_node].delegating.inc_node_negative(dnt_node)

    def good_payment(self, cnt_node, dnt_node):
        self.ranking[cnt_node].delegating.inc_node_positive(dnt_node)

    def no_payment(self, cnt_node, dnt_node):
        self.ranking[cnt_node].delegating.inc_node_negative(dnt_node)

    def ask_for_node_computing(self, cnt_node, dnt_node):
        if self.ranking[dnt_node].computing.get_node_positive(cnt_node) is None and self.ranking[
            dnt_node].computing.get_node_negative(cnt_node) is None:
            opinion = self.get_global_computing_opinion(cnt_node, dnt_node)
        else:
            opinion = self.self_computing_opinion(cnt_node, dnt_node)
        return opinion > self.computing_trust_threshold

    def get_global_computing_opinion(self, cnt_node, dnt_node):
        opinion = self.ranking[dnt_node].computing.get_global_val(cnt_node)
        if opinion is None:
            opinion = 0.0
        return opinion

    def get_global_delegating_opinion(self, cnt_node, dnt_node):
        opinion = self.ranking[dnt_node].computing.get_global_val(cnt_node)
        if opinion is None:
            opinion = 0.0
        return opinion

    def self_computing_opinion(self, cnt_node, dnt_node):
        return self.ranking[dnt_node].computing.get_node_trust(cnt_node) > self.computing_trust_threshold

    def ask_for_node_delegating(self, cnt_node, dnt_node):
        if self.ranking[cnt_node].delegating.get_node_positive(cnt_node) is None and self.ranking[
            cnt_node].delegating.get_node_negative(dnt_node) is None:
            opinion = self.get_global_delegating_opinion(dnt_node, cnt_node)
        else:
            opinion = self.self_delegating_opinion(cnt_node, dnt_node)
        return opinion > self.delegating_trust_threshold

    def self_delegating_opinion(self, cnt_node, dnt_node):
        return self.ranking[cnt_node].delegating.get_node_trust(dnt_node)

    def get_neighbours_opinion(self, node, for_node, computing):
        opinions = {}
        for n in self.network.nodes[node]:
            if computing:
                trust = self.ranking[n].computing.get_node_trust(for_node)
            else:
                trust = self.ranking[n].delegating.get_node_trust(for_node)
            opinions[n] = trust

        return opinions

    def listen_to_opinions(self, node, for_node, opinions, threshold):
        val = 0
        cnt = 0
        for node_id, opinion in opinions.iteritems():
            val += opinion
            cnt += 1
        if cnt > 0:
            neigh_opinion = float(val) / float(cnt)
        else:
            neigh_opinion = 0.0
        return neigh_opinion > threshold

    def sync_ranking(self):
        k = self.count_gossip_num_vec()
        self.start_gossip(k)
        while True:
            self.do_gossip()
            if self.gossip_step > 0 and self.stop_gossip():
                break
            self.gossip_step += 1
            if self.gossip_step >= self.gossip_max_steps:
                break
        print "GOSSIP STEP {}".format(self.gossip_step)
        self.gossip_step = 0

    def start_gossip(self, k):
        self.gossip_step = 0
        self.finished = [False, False]
        for rank in self.ranking.values():
            rank.start_diff_gossip(k[rank.node_id])

    def do_gossip(self):
        gossips = []
        for rank in self.ranking.values():
            gossips.append(rank.do_gossip(self.finished))

        self.send_gossips(gossips)

    def count_gossip_num_vec(self):
        nodes = self.ranking.keys()
        k = {}
        for node in nodes:
            degree = self.network.get_degree(node)
            neighbours_degree = self.network.get_avg_neighbours_degree(node)
            if neighbours_degree == 0.0:
                k[node] = 0
            else:
                k[node] = max(int(round(float(degree) / float(neighbours_degree))), 1)

        print k
        return k

    def send_gossips(self, gossips):
        for gossip in gossips:
            if gossip[0] is not None and len(gossip[0]) > 0:
                gossip_vec, node1 = gossip[0]
                print "gossip_vec {}, node1 {}".format(gossip_vec, node1)
                self.ranking[node1].computing.hear_gossip(gossip_vec)
                k = self.ranking[node1].computing.gossip_num
                nodes = self.get_random_neighbours(node1, k)
                for node in nodes:
                    self.ranking[node].computing.hear_gossip(gossip_vec)
            if gossip[1] is not None and len(gossip[1]) > 0:
                gossip_vec, node1 = gossip[1]
                self.ranking[node1].delegating.hear_gossip(gossip_vec)
                k = self.ranking[node1].delegating.gossip_num
                nodes = self.get_random_neighbours(node1, k)
                for node in nodes:
                    self.ranking[node].computing.hear_gossip(gossip_vec)

    def get_random_neighbours(self, node_id, k):
        return random.sample(self.network.nodes[node_id], k)

    def stop_gossip(self):
        nodes = self.ranking.keys()
        for node in nodes:
            self.ranking[node].stop_gossip(self.finished)
        stopped_com = 0
        stopped_del = 0
        print self.finished
        for node in nodes:
            if not self.finished[0]:
                neighbours_stopeed = True
                if self.ranking[node].computing.is_stopped():

                    for neigh in self.network.nodes[node]:
                        if not self.ranking[neigh].computing.is_stopped():
                            neighbours_stopeed = False
                    if neighbours_stopeed:
                        self.ranking[node].computing.neigh_stopped()
                        stopped_com += 1
            if not self.finished[1]:
                neighbours_stopeed = True
                if self.ranking[node].delegating.is_stopped():
                    for neigh in self.network.nodes[node]:
                        if not self.ranking[neigh].delegating.is_stopped():
                            neighbours_stopeed = False
                    if neighbours_stopeed:
                        self.ranking[node].delegating.neigh_stopped()
                        stopped_del += 1
        print "STOPPED {} {}".format(stopped_com, stopped_del)
        if stopped_com == len(nodes):
            self.finished[0] = True
        if stopped_del == len(nodes):
            self.finished[1] = True

        return self.finished[0] and self.finished[1]


def main():
    rs = DifferentialGossipTrustSimulator()

    for i in range(0, 1):
        rs.full_add_node(good_node=False)
    for i in range(0, 5):
        rs.full_add_node(good_node=True)
    rs.print_state()
    rs.sync_network()

    print "################"
    for i in range(0, 5):
        rs.sync_network()
        rs.start_task(random.sample(rs.ranking.keys(), 1)[0])

        rs.sync_ranking()
    rs.print_state()


if __name__ == "__main__":
    main()
