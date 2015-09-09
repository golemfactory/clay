import sys
import os
import random
from copy import copy

sys.path.append(os.environ.get('GOLEM'))

from golem.ranking.simpleRank import SimpleRank
from networkSimulator import PANetworkSimulator

class RankSimulator:
    def __init__(self, rank_class, opt_peers = 2, network = PANetworkSimulator):
        self.network = network()
        self.ranking = {}
        self.behaviour = {}
        self.nodes_cnt = 0
        self.rank_class = rank_class
        self.opt_peers = opt_peers
        self.last_node = None

    def get_last_node_name(self):
        return self.last_node

    def add_node(self, good_node = True):
        node = self.network.add_node()
        self.ranking[ node ] = self.rank_class()
        self.behaviour[ node ] = good_node
        self.last_node = node

    def full_add_node(self, good_node = True):
        self.add_node(good_node)
        self.sync_network()

    def connect_node(self, node):
        self.network.connect_node(node)

    def sync_network(self):
        self.network.sync_network(self.opt_peers)

    def print_state(self):
        for node, nodeData in self.network.nodes.iteritems():
            print "{}: {}, peers {}\n".format(node, self.ranking[node], nodeData)

    def start_task(self, node):
        if node not in self.ranking:
            print "Wrong node {}".format(node)

        counting_nodes = self.ranking.keys()
        for n in random.sample(counting_nodes, self.num_nodes_task()):
            if n != node:
                if self.ask_for_node_delegating(n, node) and self.ask_for_node_computing(node, n):
                    self.count_task(n, node)

    def ask_for_node_delegating(self, cnt_node, dnt_node):
        return True

    def ask_for_node_computing(self, cnt_node, dnt_node):
        return True

    def num_nodes_task(self):
        return 3

    def count_task(self, cnt_node, dnt_node):
        if cnt_node not in self.ranking:
            print "Wrong node {}".format(cnt_node)
        if dnt_node not in self.ranking:
            print "Wrong node {}".format(dnt_node)

        if self.behaviour[cnt_node]:
            self.good_counting(cnt_node, dnt_node)
            if self.behaviour[dnt_node]:
                self.good_payment(cnt_node, dnt_node)
            else:
                self.no_payment(cnt_node, dnt_node)
        else:
            self.bad_counting(cnt_node, dnt_node)


    def good_counting(self, cnt_node, dnt_node):
        pass

    def bad_counting(self, cnt_node, dnt_node):
        pass

    def good_payment(self, cnt_node, dnt_node):
        pass

    def no_payment(self, cnt_node, dnt_node):
        pass



class SimpleRankSimulator(RankSimulator):
    def __init__(self, opt_peers = 3, trust_threshold  = 0.2, nodes_for_task = 2, good_task_reward = 0.1,
                  bad_task_punishment = 0.2, payment_reward = 0.2, bad_payment_punishment = 0.3):
        RankSimulator.__init__(self, SimpleRank, opt_peers)
        self.trust_threshold = trust_threshold
        self.nodes_for_task = nodes_for_task
        self.good_task_reward = good_task_reward
        self.bad_task_punishment = bad_task_punishment
        self.payment_reward = payment_reward
        self.bad_payment_punishment = bad_payment_punishment

    def num_nodes_task(self):
        return self.nodes_for_task

    def good_counting(self, cnt_node, dnt_node):
        self.add_to_rank(dnt_node, cnt_node, self.good_task_reward)

    def bad_counting(self, cnt_node, dnt_node):
        self.add_to_rank(dnt_node, cnt_node, - self.bad_task_punishment)
        self.add_to_rank(cnt_node, dnt_node, - self.bad_payment_punishment)

    def good_payment(self, cnt_node, dnt_node):
        self.add_to_rank(cnt_node, dnt_node, self.payment_reward)

    def no_payment(self, cnt_node, dnt_node):
        self.add_to_rank(cnt_node, dnt_node, -self.bad_payment_punishment)

    def add_to_rank(self, in_node, for_node, value):
        self.ranking[in_node].set_node_rank(for_node, self.get_global_rank(in_node, for_node) + value)

    def ask_for_node_delegating(self, cnt_node, dnt_node):
        return self.ask_for_node(cnt_node, dnt_node)

    def ask_for_node_computing(self, dnt_node, cnt_node):
        return self.ask_for_node(dnt_node, cnt_node)

    def ask_for_node(self, node, for_node):
        if node not in self.ranking:
            print "Wrong node {}".format(node)
        if for_node not in self.ranking:
            print "Wrong node {}".format(for_node)

        other_rank = {}
        for peer in self.network.nodes[node]:
            other_rank[peer] = self.ranking[peer].get_node_rank(for_node)

        test = self.ranking[node].global_node_rank(for_node, other_rank)
        if test > self.trust_threshold:
            return True
        else:
            if for_node in self.network.nodes[node]:
                self.network.nodes[node].remove(for_node)
            return False

    def get_global_rank(self, node, for_node):
        other_rank = {}
        for peer in self.network.nodes[node]:
            other_rank[peer] = self.ranking[peer].get_node_rank(for_node)

        return self.ranking[node].global_node_rank(for_node, other_rank)


def main():
    rs = SimpleRankSimulator()
    for i in range(0, 5):
        rs.full_add_node(good_node = False)
    for i in range(0, 10):
        rs.full_add_node(good_node = True)

    rs.print_state()
    print "################"
    for i in range(0, 200):
        rs.start_task(random.sample(rs.ranking.keys(), 1)[0])
    rs.print_state()


if __name__ == "__main__":
    main()

