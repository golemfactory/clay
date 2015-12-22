import random
from numpy import matrix
from collections import OrderedDict
from golem.ranking.gossiptrustrank import GossipTrustTest, GossipPositiveNegativeTrustRank
from ranksimulator import RankSimulator


class GossipTrustNodeRank:
    def __init__(self):
        self.computing = GossipPositiveNegativeTrustRank()
        self.delegating = GossipPositiveNegativeTrustRank()
        self.node_id = None

    def set_node_id(self, node_id):
        self.node_id = node_id
        self.computing.set_node_id(node_id)
        self.delegating.set_node_id(node_id)

    def set_seed_rank(self, seed_node):
        pass

    def __str__(self):
        return "Computing: {}, ".format(self.computing) + "Delegating: {} ".format(self.delegating)

    def start_aggregation(self):
        self.computing.start_aggregation()
        self.delegating.start_aggregation()

    def stop_aggregation(self, finished, stop):
        [stop_pos, stop_neg] = self.computing.stop_aggregation(finished[0], finished[1])
        if stop_pos:
            stop[0] += 1
        if stop_neg:
            stop[1] += 1
        [stop_pos, stop_neg] = self.computing.stop_aggregation(finished[2], finished[3])
        if stop_pos:
            stop[2] += 1
        if stop_neg:
            stop[3] += 1

    def stop_gossip(self, finished, stop):
        [stop_pos, stop_neg] = self.computing.stop_gossip(finished[0], finished[1])
        if stop_pos:
            stop[0] += 1
        if stop_neg:
            stop[1] += 1
        [stop_pos, stop_neg] = self.computing.stop_gossip(finished[2], finished[3])
        if stop_pos:
            stop[2] += 1
        if stop_neg:
            stop[3] += 1

    def prep_aggregation(self, finished):
        self.computing.prep_aggregation(finished[0], finished[1])
        self.delegating.prep_aggregation(finished[2], finished[3])

    def do_gossip(self, finished):
        gossip = [None, None]
        gossip[0] = self.computing.do_gossip(finished[0], finished[1])
        gossip[1] = self.delegating.do_gossip(finished[2], finished[3])
        return gossip


class GossipTrustSimulator(RankSimulator):
    def __init__(self, opt_peers=3, agg_max_steps=3, gossip_max_steps=3):
        RankSimulator.__init__(self, GossipTrustNodeRank, opt_peers)
        self.global_ranks = {}
        self.agg_max_steps = agg_max_steps
        self.gossip_max_steps = gossip_max_steps
        self.agg_steps = 0
        self.gossip_steps = 0
        self.finished = [False] * 4
        self.finished_gossips = [False] * 4

    def add_node(self, good_node=True):
        RankSimulator.add_node(self, good_node)
        node_id = 'node{}'.format(str(self.nodes_cnt).zfill(3))
        self.nodes[node_id]['global_ranking'] = {}
        self.nodes[node_id]['ranking'].set_node_id(node_id)
        self.nodes[node_id]['ranking'].computing.negative.print_data = True

    def good_counting(self, cnt_node, dnt_node):
        self.nodes[dnt_node]['ranking'].computing.inc_node_positive(cnt_node)

    def bad_counting(self, cnt_node, dnt_node):
        self.nodes[dnt_node]['ranking'].computing.inc_node_negative(cnt_node)
        self.nodes[cnt_node]['ranking'].delegating.inc_node_negative(dnt_node)

    def good_payment(self, cnt_node, dnt_node):
        self.nodes[cnt_node]['ranking'].delegating.inc_node_positive(dnt_node)

    def no_payment(self, cnt_node, dnt_node):
        self.nodes[cnt_node]['ranking'].delegating.inc_node_negative(dnt_node)

    def ask_for_node_computing(self, cnt_node, dnt_node):
        return True
        # return self.nodes[dnt_node]['ranking'].computing.negative.get_node_trust(cnt_node) < 1.0

    def ask_for_node_delegating(self, cnt_node, dnt_node):
        return True
        #  return self.nodes[cnt_node]['ranking'].delegating.negative.get_node_trust(dnt_node) < 1.0

    def sync_ranking(self):
        print "SYNC RANKING"
        while True:
            self.do_aggregation_step()
            if self.stop_aggregation():
                break
            self.agg_steps += 1
            if self.agg_steps >= self.agg_max_steps:
                break
        print "AGG STEP {}".format(self.agg_steps)
        self.agg_steps = 0

    def start_aggregation(self):
        for node_id, node in self.nodes.iteritems():
            node['ranking'].start_aggregation()
        self.finished = [False, False, False, False]
        self.agg_steps = 0

    def stop_aggregation(self):
        stop = [0, 0, 0, 0]
        for node_id, node in self.nodes.iteritems():
            node['ranking'].stop_aggregation(self.finished, stop)
        for i in range(0, 4):
            if stop[i] == len(self.nodes):
                self.finished[i] = True
        for i in range(0, 4):
            if not self.finished[i]:
                return False
        return True

    def prep_aggregation(self):
        for node_id, node in self.nodes.iteritems():
            node['ranking'].prep_aggregation(self.finished)
        self.gossip_steps = 0
        self.finished_gossips = self.finished

    def do_aggregation_step(self):
        if self.agg_steps == 0:
            self.start_aggregation()
        else:
            self.prep_aggregation()

        while True:
            self.do_gossip()
            if self.stop_gossip():
                break
            self.gossip_steps += 1
            if self.gossip_steps >= self.gossip_max_steps:
                break
        print "GOSSIP STEP {}".format(self.gossip_steps)
        self.gossip_steps = 0

    def stop_gossip(self):
        stop = [0, 0, 0, 0]
        for node_id, node in self.nodes.iteritems():
            node['ranking'].stop_gossip(self.finished_gossips, stop)
        same = self.same_vec()
        for i in range(0, 4):
            if stop[i] == len(self.nodes) and same[i]:
                self.finished_gossips[i] = True
        for i in range(0, 4):
            if not self.finished_gossips[i]:
                return False
        return True

    def same_vec(self):
        vec = [{}, {}, {}, {}]
        ret = [None, None, None, None]
        for node_id, node in self.nodes.iteritems():
            for glob_node_id, glob_val in node['ranking'].computing.positive.glob_vec.iteritems():
                if glob_node_id not in vec[0]:
                    vec[0][glob_node_id] = count_div(glob_val[0], glob_val[1])
                else:
                    if abs(vec[0][glob_node_id] - count_div(glob_val[0], glob_val[1])) > 0.1:
                        ret[0] = False
                        break
            for glob_node_id, glob_val in node['ranking'].computing.negative.glob_vec.iteritems():
                if glob_node_id not in vec[1]:
                    vec[1][glob_node_id] = count_div(glob_val[0], glob_val[1])
                else:
                    if abs(vec[1][glob_node_id] - count_div(glob_val[0], glob_val[1])) > 0.1:
                        ret[1] = False
                        break
            for glob_node_id, glob_val in node['ranking'].delegating.positive.glob_vec.iteritems():
                if glob_node_id not in vec[2]:
                    vec[2][glob_node_id] = count_div(glob_val[0], glob_val[1])
                else:
                    if abs(vec[2][glob_node_id] - count_div(glob_val[0], glob_val[1])) > 0.1:
                        ret[2] = False
                        break
            for glob_node_id, glob_val in node['ranking'].delegating.negative.glob_vec.iteritems():
                if glob_node_id not in vec[3]:
                    vec[3][glob_node_id] = count_div(glob_val[0], glob_val[1])
                else:
                    if abs(vec[3][glob_node_id] - count_div(glob_val[0], glob_val[1])) > 0.1:
                        ret[3] = False
                        break
        for i in range(0, 4):
            if ret[i] is None:
                ret[i] = True
        return ret

    def count_div(self, a, b):
        if a == 0.0:
            return 0.0
        if b == 0.0:
            return float("inf")
        return float(a) / float(b)

    def do_gossip(self):
        gossips = []

        for node_id, node in self.nodes.iteritems():
            gossips.append(node['ranking'].do_gossip(self.finished_gossips))

        self.send_gossips(gossips)

    def send_gossips(self, gossips):
        for gossip in gossips:
            if gossip[0] is not None:
                if gossip[0][0] is not None:
                    gossip_vec, node1 = gossip[0][0]
                    node2 = self.get_second_node(node1)
                    self.nodes[node1]['ranking'].computing.positive.hear_gossip(gossip_vec)
                    self.nodes[node2]['ranking'].computing.positive.hear_gossip(gossip_vec)
                if gossip[0][1] is not None:
                    gossip_vec, node1 = gossip[0][1]
                    node2 = self.get_second_node(node1)
                    self.nodes[node1]['ranking'].computing.negative.hear_gossip(gossip_vec)
                    self.nodes[node2]['ranking'].computing.negative.hear_gossip(gossip_vec)
            if gossip[1] is not None:
                if gossip[1][0] is not None:
                    gossip_vec, node1 = gossip[1][0]
                    node2 = self.get_second_node(node1)
                    self.nodes[node1]['ranking'].delegating.positive.hear_gossip(gossip_vec)
                    self.nodes[node2]['ranking'].delegating.positive.hear_gossip(gossip_vec)
                if gossip[1][1] is not None:
                    gossip_vec, node1 = gossip[1][1]
                    node2 = self.get_second_node(node1)
                    self.nodes[node1]['ranking'].delegating.negative.hear_gossip(gossip_vec)
                    self.nodes[node2]['ranking'].delegating.negative.hear_gossip(gossip_vec)

    def get_second_node(self, node1):
        r = random.sample(self.nodes.keys(), 1)
        if len(self.nodes) > 1:
            while r == node1:
                r = random.sample(self.nodes.keys(), 1)
        return r[0]


def count_div(a, b):
    if a == 0.0:
        return 0.0
    if b == 0.0:
        return float("inf")
    return float(a) / float(b)


def make_gossip_trust_test():
    gtr = GossipTrustTest(delta=0.1)
    gtr.add_node('abc')
    gtr.add_node('def')
    gtr.add_node('ghi')
    print gtr.local_ranking
    print gtr.local_ranking_mapping
    print gtr.global_ranking
    gtr.local_ranking[0, 1] = 0.2
    gtr.local_ranking[1, 1] = 0
    gtr.local_ranking[2, 1] = 0.6
    print gtr.local_ranking
    gtr.global_ranking = matrix([[1.0 / 2.0], [1.0 / 3.0], [1.0 / 6.0]])
    print gtr.global_ranking
    gtr.do_gossip('def')
    print gtr.previous_score
    print gtr.weighted_scores
    print gtr.consensus_factors
    print [gtr.weighted_scores[i] / gtr.consensus_factors[i] for i in range(0, 3)]
    print gtr.gossip_score_steps


def main():
    rs = GossipTrustSimulator()
    for i in range(0, 1):
        rs.full_add_node(good_node=False)
    for i in range(0, 2):
        rs.full_add_node(good_node=True)

    rs.print_state()
    print "################"
    for i in range(0, 3):
        rs.start_task(random.sample(rs.nodes.keys(), 1)[0])
        #  rs.sync_ranking()
    rs.print_state()
    rs.sync_ranking()
    rs.print_state()
    print "Positive"
    nd = OrderedDict(sorted(rs.nodes.items(), key=lambda t: t[0]))
    for node_id, node in nd.iteritems():
        d = OrderedDict(sorted(node['ranking'].computing.positive.glob_vec.items(), key=lambda t: t[0]))
        for n_id, val in d.iteritems():
            d[n_id] = count_div(val[0], val[1])
        print "{}: {}\n".format(node_id, d)

    print "Negative"
    for node_id, node in nd.iteritems():
        d = OrderedDict(sorted(node['ranking'].computing.negative.glob_vec.items(), key=lambda t: t[0]))
        for n_id, val in d.iteritems():
            d[n_id] = count_div(val[0], val[1])
        print "{}: {}\n".format(node_id, d)


if __name__ == "__main__":
    main()
