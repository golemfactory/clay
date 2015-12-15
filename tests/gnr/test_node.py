import unittest
from examples.gnr.node import parse_peer


class TestParseConnect(unittest.TestCase):
    def test_parse_peer(self):
        addr = parse_peer(None, "connect", ("127.0.0.1:15", ))
        self.assertEqual(len(addr), 1)
        self.assertEqual(addr[0].address, "127.0.0.1")
        self.assertEqual(addr[0].port, 15)

        addr = parse_peer(None, "connect", ("127.0.0.2:30", "blargh"))
        self.assertEqual(len(addr), 1)
        self.assertEqual(addr[0].address, "127.0.0.2")
        self.assertEqual(addr[0].port, 30)

        addr = parse_peer(None, "connect", ("10.32.10.33:abc", "10.32.10.33:10", "abc:30"))
        self.assertEqual(len(addr), 2)
        self.assertEqual(addr[0].address, "10.32.10.33")
        self.assertEqual(addr[0].port, 10)
        self.assertEqual(addr[1].port, 30)

    def test_parse_peer_ip6(self):
        addr = parse_peer(None, "connect", ("10.30.12.13:45", "[::ffff:0:0:0]:96", "10.30.10.12:3013",
                             "[2001:db8:85a3:8d3:1319:8a2e:370:7348]:443"))
        self.assertEqual(len(addr), 4)
        self.assertEqual(addr[1].address, "::ffff:0:0:0")
        self.assertEqual(addr[1].port, 96)
        self.assertEqual(addr[2].address, "10.30.10.12")
        self.assertEqual(addr[2].port, 3013)
        self.assertEqual(addr[3].address, "2001:db8:85a3:8d3:1319:8a2e:370:7348")
        self.assertEqual(addr[3].port, 443)
