import unittest

from golem.ethereum import Client


class EthereumClientTest(unittest.TestCase):
    def test_client(self):
        client = Client()
        p = client.get_peer_count()
        assert type(p) is int
        s = client.is_syncing()
        assert type(s) is bool
        addr = b'FakeEthereumAddress!'
        assert len(addr) == 20
        c = client.get_transaction_count(addr.encode('hex'))
        assert type(c) is int
        assert c == 0

    def test_send_transaction(self):
        client = Client()
        self.assertRaises(ValueError,
                          lambda: client.send_raw_transaction("fake data"))

    def test_start_terminate(self):
        client = Client()
        client._Client__terminate_client_subprocess()
