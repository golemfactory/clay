import unittest
from golem.ranking.simplerank import SimpleRank


class TestSimpleRank(unittest.TestCase):

    def testRank(self):
        sr = SimpleRank()
        self.assertIsNone(sr.get_node_rank('abc'))
        sr.set_node_rank('abc', 1.0)
        self.assertEquals(sr.get_node_rank('abc'), 1.0)
        sr.set_node_rank('def', 0.3)
        self.assertEquals(sr.get_node_rank('def'), 0.3)
        sr.set_node_rank('ghi', -1.2)
        self.assertEquals(sr.get_node_rank('ghi'), 0.0)
        sr.set_node_rank('ghi', 3.0)
        self.assertEquals(sr.get_node_rank('ghi'), 1.0)

    def testNetworkRank(self):
        node1 = SimpleRank()
        node2 = SimpleRank()
        # 2 dolacza do sieci
        node2.set_seed_rank('node1')
        node1.set_basic_node_rank('node2')
        print "Node1: {}".format(node1.ranking)
        print "Node2: {}".format(node2.ranking)
        # 3 dolacza do sieci z 1
        node3 = SimpleRank()
        node3.set_seed_rank('node1')
        node1.set_basic_node_rank('node3')
        node2.set_node_rank('node3', {'node1': node1.get_node_rank('node3')})
        node3.set_node_rank('node2', {'node2': node1.get_node_rank('node2')})
        print "Node1: {}".format(node1.ranking)
        print "Node2: {}".format(node2.ranking)
        print "Node3: {}".format(node3.ranking)
        # 2 chce cos policzyc
        node1.set_node_rank('node2', {'node3': node1.get_node_rank('node2')})
        node3.set_node_rank('node2', {'node1': node3.get_node_rank('node2')})
        print "Node1: {}".format(node1.ranking)
        print "Node2: {}".format(node2.ranking)
        print "Node3: {}".format(node3.ranking)
        # 3 policzyla poprawnie
        node2.set_node_rank('node3', node2.get_node_rank('node3') + 0.1)
        # 1 policzyla poprawnie
        node2.set_node_rank('node1', node2.get_node_rank('node1') + 0.1)
        # 2 zaplacila
        node3.set_node_rank('node2', node3.get_node_rank('node2') + 0.15)
        node1.set_node_rank('node2', node1.get_node_rank('node2') + 0.15)
        print "Node1: {}".format(node1.ranking)
        print "Node2: {}".format(node2.ranking)
        print "Node3: {}".format(node3.ranking)
        # 4 dolacza do sieci
        node4 = SimpleRank()
        node4.set_seed_rank('node2 ')
        node2.set_basic_node_rank('node4')
        # 4 chce liczyc
        node1.set_node_rank(
            'node4', {'node2': node2.get_node_rank('node4'), 'node3': node3.get_node_rank('node4')})
        node2.set_node_rank(
            'node4', {'node1': node1.get_node_rank('node4'), 'node3': node3.get_node_rank('node4')})
        node3.set_node_rank(
            'node4', {'node2': node2.get_node_rank('node4'), 'node1': node1.get_node_rank('node4')})
        node4.set_node_rank('node1', {'node2': node2.get_node_rank('node1')})
        node4.set_node_rank('node2', {'node1': node1.get_node_rank('node2')})
        node4.set_node_rank(
            'node3', {'node2': node2.get_node_rank('node3'), 'node1': node1.get_node_rank('node3')})
        print "Node1: {}".format(node1.ranking)
        print "Node2: {}".format(node2.ranking)
        print "Node3: {}".format(node3.ranking)
        print "Node4: {}".format(node4.ranking)
