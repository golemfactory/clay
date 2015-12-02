import unittest
import rlp
from golem.network.p2p.node import Node


class NodeTest(unittest.TestCase):

    def test_node_rlp(self):
        node = Node()
        node.node_id = 'node1'
        node.prv_port = 80
        node.pub_port = 16080
        node.prv_addr = "helloworld.io"
        node.prv_addresses.append('a')
        e = rlp.encode(node)
        d = rlp.decode(e, Node)
        self.assertEqual(d, node)
        self.assertEqual(d.node_id, 'node1')
        self.assertEqual(d.prv_addresses[0], 'a')

    def test_node_collect(self):
        node = Node()
        node.collect_network_info()
        e = rlp.encode(node)
        d = rlp.decode(e, Node)
        self.assertEqual(d, node)
        self.assertEqual(d.pub_addr, node.pub_addr)
