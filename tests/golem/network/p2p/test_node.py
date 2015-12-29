import unittest
from golem.network.p2p.node import Node


class TestNode(unittest.TestCase):
    def test_str(self):
        n = Node()
        n.node_name = "Blabla"
        n.key = "ABC"
        self.assertFalse("at" in str(n))
        self.assertFalse("at" in "{}".format(n))
        self.assertTrue("Blabla" in str(n))
        self.assertTrue("Blabla" in "{}".format(n))
        self.assertTrue("ABC" in str(n))
        self.assertTrue("ABC" in "{}".format(n))

