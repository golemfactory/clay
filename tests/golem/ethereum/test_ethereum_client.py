import logging
import unittest

from golem.ethereum import Client


class EthereumClientTest(unittest.TestCase):
    def setUp(self):
        # Show information about Ethereum node starting and terminating.
        logging.basicConfig(level=logging.INFO)

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

    # @unittest.skip("This is quite fragile and affects other tests")
    def test_start_terminate(self):
        client = Client()
        assert client.node.is_running()
        client.node.stop()
        assert not client.node.is_running()
        client.node.start(rpc=False)
        assert client.node.is_running()
        client.node.stop()
        assert not client.node.is_running()
