import random

from golem.ranking.eigenTrustRank import EigenTrustRank
from rankSimulator import RankSimulator

class EigenTrustNodeRank:
    def __init__(self):
        self.computing = EigenTrustRank()
        self.delegating = EigenTrustRank()

    def set_seed_rank(self, seed_node):
        pass

    def __str__(self):
        return "Computing: {}, ".format(self.computing) +"Delegating: {}, ".format(self.delegating)



class EigenTrustSimulator(RankSimulator):
    def __init__(self, opt_peers = 3, trust_threshold = -1.0):
        RankSimulator.__init__(self, EigenTrustNodeRank, opt_peers)
        self.trust_threshold = trust_threshold

    def good_counting(self, cnt_node, dnt_node):
        self.nodes[ dnt_node ]['ranking'].computing.inc_node_positive(cnt_node)

    def bad_counting(self, cnt_node, dnt_node):
        self.nodes[ dnt_node ]['ranking'].computing.inc_node_negative(cnt_node)
        self.nodes[ cnt_node ]['ranking'].delegating.inc_node_negative(dnt_node)

    def good_payment(self, cnt_node, dnt_node):
        self.nodes[ cnt_node ]['ranking'].delegating.inc_node_positive(dnt_node)

    def no_payment(self, cnt_node, dnt_node):
        self.nodes[ cnt_node ]['ranking'].delegating.inc_node_negative(dnt_node)


    def ask_for_node_computing(self, dnt_node, cnt_node):
        if cnt_node not in self.nodes:
            print "Wrong node {}".format(cnt_node)
        if dnt_node not in self.nodes:
            print "Wrong node {}".format(dnt_node)

        other_ranks = {}
        for peer in self.nodes[ dnt_node ]['peers']:
            other_ranks[peer] = self.nodes[peer]['ranking'].computing.get_node_trust(cnt_node)

        test = self.nodes[dnt_node]['ranking'].computing.get_global_trust(cnt_node, other_ranks)
        print "DNT NODE {}, CNT NODE{} GLOBAL {}".format(dnt_node, cnt_node, test)
        if test > self.trust_threshold:
            return True
        else:
            return False

    def ask_for_node_delegating(self, cnt_node, dnt_node):
        if cnt_node not in self.nodes:
            print "Wrong node {}".format(cnt_node)
        if dnt_node not in self.nodes:
            print "Wrong node {}".format(dnt_node)

        other_ranks = {}
        for peer in self.nodes[ cnt_node ]['peers']:
            other_ranks[peer] = self.nodes[peer]['ranking'].delegating.get_node_trust(dnt_node)

        test = self.nodes[cnt_node]['ranking'].delegating.get_global_trust(dnt_node, other_ranks)
        print "CNT NODE {}, DNT NODE{} GLOBAL {}".format(cnt_node, dnt_node, test)
        if test > self.trust_threshold:
            return True
        else:
            return False



def main():
    rs = EigenTrustSimulator()
    for i in range(0, 1):
        rs.full_add_node(good_node = False)
    for i in range(0, 10):
        rs.full_add_node(good_node = True)

    rs.print_state()
    print "################"
    for i in range(0, 100):
        rs.start_task(random.sample(rs.nodes.keys(), 1)[0])
    rs.print_state()



if __name__ == "__main__":
    main()
