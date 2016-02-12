import unittest

from golem.ethereum import Client


class EthereumClientTest(unittest.TestCase):
    def test_client(self):
        client = Client()
        p = client.get_peer_count()
        assert type(p) is int
        s = client.is_syncing()
        assert type(s) is bool
        c = client.get_transaction_count(b'Fake Ethereum Address')
        assert type(c) is int

    def test_send_transaction(self):
        client = Client()
        self.assertRaises(ValueError,
                          lambda: client.send_raw_transaction("fake data"))
