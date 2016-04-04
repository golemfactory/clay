import unittest

from golem.utils import find_free_net_port


class FreePortTest(unittest.TestCase):
    def test_free_port_selector(self):
        port = find_free_net_port()
        assert port >= 1024 and port <= 2**16
