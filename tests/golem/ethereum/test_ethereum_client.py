import logging
import unittest

from ethereum.transactions import Transaction
from ethereum.utils import zpad
from mock import patch

from golem.ethereum import Client
from golem.ethereum.node import NodeProcess
from golem.testutils import TempDirFixture


class EthereumClientTest(TempDirFixture):
    def setUp(self):
        super(EthereumClientTest, self).setUp()
        # Show information about Ethereum node starting and terminating.
        logging.basicConfig(level=logging.INFO)
        self.client = Client(self.tempdir)

    def tearDown(self):
        self.client.node.stop()
        super(EthereumClientTest, self).tearDown()

    def test_client(self):
        client = self.client
        p = client.get_peer_count()
        assert type(p) is int
        s = client.is_syncing()
        assert type(s) is bool
        addr = b'FakeEthereumAddress!'
        assert len(addr) == 20
        c = client.get_transaction_count('0x' + addr.encode('hex'))
        assert type(c) is int
        assert c == 0

    def test_send_raw_transaction(self):
        client = self.client
        with self.assertRaises(ValueError):
            client.send("fake data")
        client.node.stop()

    def test_send_transaction(self):
        client = self.client
        addr = '\xff' * 20
        priv = '\xee' * 32
        tx = Transaction(1, 20 * 10**9, 21000, to=addr, value=0, data=b'')
        tx.sign(priv)
        with self.assertRaisesRegexp(ValueError, "[Ii]nsufficient funds"):
            client.send(tx)

    def test_start_terminate(self):
        client = self.client
        assert client.node.is_running()
        client.node.stop()
        assert not client.node.is_running()
        client.node.start()
        assert client.node.is_running()
        client.node.stop()
        assert not client.node.is_running()

    def test_get_logs(self):
        addr = '0x' + zpad('deadbeef', 32).encode('hex')
        log_id = '0x' + zpad('beefbeef', 32).encode('hex')
        client = self.client
        logs = client.get_logs(from_block='latest', to_block='latest',
                               topics=[log_id, addr])
        assert logs == []

    def test_filters(self):
        """ Test creating filter and getting logs """
        client = self.client
        filter_id = client.new_filter()
        assert type(filter_id) is unicode
        # Filter id is hex encoded 256-bit integer.
        assert filter_id.startswith('0x')
        number = int(filter_id, 16)
        assert 0 < number < 2**256

        entries = client.get_filter_changes(filter_id)
        assert not entries
