import logging
import time
from unittest import mock

from ethereum.transactions import Transaction
from ethereum.utils import zpad

from golem.ethereum import Client
from golem.testutils import TempDirFixture
from golem.utils import encode_hex

SYNC_TEST_INTERVAL = 0.01


class EthereumClientNodeTest(TempDirFixture):
    def setUp(self):
        super().setUp()
        # Show information about Ethereum node starting and terminating.
        logging.basicConfig(level=logging.INFO)
        self.client = Client(self.tempdir, start_node=True)

    def tearDown(self):
        self.client.node.stop()
        super().tearDown()

    def test_client(self):
        client = self.client
        p = client.get_peer_count()
        assert type(p) is int
        s = client.is_syncing()
        assert type(s) is bool
        addr = b'FakeEthereumAddress!'
        assert len(addr) == 20
        hex_addr = '0x' + encode_hex(addr)
        c = client.get_transaction_count(hex_addr)
        assert type(c) is int
        assert c == 0
        b = client.get_balance(hex_addr)
        assert b == 0

        eth = client.web3.eth
        with mock.patch.object(eth, 'getBalance', side_effect=ValueError):
            b = client.get_balance(hex_addr)
        assert b is None

    def test_send_raw_transaction(self):
        client = self.client
        with self.assertRaises(ValueError):
            client.send("fake data")
        client.node.stop()

    def test_send_transaction(self):
        client = self.client
        addr = b'\xff' * 20
        priv = b'\xee' * 32
        tx = Transaction(1, 20 * 10**9, 21000, to=addr, value=0, data=b'')
        tx.sign(priv)
        with self.assertRaisesRegex(ValueError, "[Ii]nsufficient funds"):
            client.send(tx)

    def test_start_terminate(self):
        client = self.client
        assert client.node.is_running()
        client.node.stop()
        assert not client.node.is_running()

    def test_get_logs(self):
        addr = encode_hex(zpad(b'deadbeef', 32))
        log_id = encode_hex(zpad(b'beefbeef', 32))
        client = self.client
        logs = client.get_logs(from_block='latest', to_block='latest',
                               topics=[log_id, addr])
        assert logs == []

    def test_filters(self):
        """ Test creating filter and getting logs """
        client = self.client
        filter_id = client.new_filter()
        assert type(filter_id) is str
        # Filter id is hex encoded 256-bit integer.
        assert filter_id.startswith('0x')
        number = int(filter_id, 16)
        assert 0 < number < 2**256

        entries = client.get_filter_changes(filter_id)
        assert not entries


class EthereumClientTest(TempDirFixture):
    def setUp(self):
        super().setUp()
        self.client = Client(self.tempdir, start_node=False)
        self.client.web3 = mock.Mock()

    def check_synchronized(self):
        assert not self.client.is_synchronized()
        self.client.web3.net.peerCount = 1
        self.client.web3.eth.syncing = {
            "currentBlock": 1,
            "highestBlock": 1,
        }
        self.assertFalse(self.client.is_synchronized())
        tmp = Client.SYNC_CHECK_INTERVAL = SYNC_TEST_INTERVAL
        time.sleep(1.5 * self.client.SYNC_CHECK_INTERVAL)
        self.assertFalse(self.client.is_synchronized())
        time.sleep(1.5 * self.client.SYNC_CHECK_INTERVAL)
        self.assertTrue(self.client.is_synchronized())
        Client.SYNC_CHECK_INTERVAL = tmp

    def test_synchronized2(self):
        self.check_synchronized()

    def test_wait_until_synchronized(self):
        Client.SYNC_CHECK_INTERVAL = SYNC_TEST_INTERVAL
        self.client.web3.net.peerCount = 1
        self.client.web3.eth.syncing = {
            "currentBlock": 1,
            "highestBlock": 1,
        }
        self.assertTrue(self.client.wait_until_synchronized())

    def test_synchronized(self):
        tmp = Client.SYNC_CHECK_INTERVAL
        Client.SYNC_CHECK_INTERVAL = SYNC_TEST_INTERVAL
        syncing_status = {'startingBlock': '0x384',
                          'currentBlock': '0x386',
                          'highestBlock': '0x454'}
        combinations = ((0, False),
                        (0, syncing_status),
                        (1, False),
                        (1, syncing_status),
                        (65, syncing_status),
                        (65, False))

        self.client.web3.eth.syncing = {
            'currentBlock': 123,
            'highestBlock': 1234,
        }
        self.client.web3.eth.getBlock.return_value = {"timestamp": time.time()}

        for c in combinations:
            print("Subtest {}".format(c))
            # Allow reseting the status.
            time.sleep(1.5 * Client.SYNC_CHECK_INTERVAL)
            self.client.web3.net.peerCount = 0
            self.assertFalse(self.client.is_synchronized())
            time.sleep(1.5 * Client.SYNC_CHECK_INTERVAL)
            self.client.web3.net.peerCount = c[0]
            self.client.web3.eth.syncing = c[1]
            # First time is always no.a
            self.assertFalse(self.client.is_synchronized())
            time.sleep(1.5 * Client.SYNC_CHECK_INTERVAL)
            self.assertTrue(self.client.is_synchronized() == (c[0] and not c[1]))  # noqa
        Client.SYNC_CHECK_INTERVAL = tmp

    def test_synchronized_unstable(self):
        tmp = Client.SYNC_CHECK_INTERVAL
        Client.SYNC_CHECK_INTERVAL = SYNC_TEST_INTERVAL
        syncing_status = {
            'startingBlock': '0x0',
            'currentBlock': '0x1',
            'highestBlock': '0x4096',
        }
        synced_status = {
            'startingBlock': '0x0',
            'currentBlock': '0x1',
            'highestBlock': '0x1',
        }

        self.client.web3.net.peerCount = 1
        self.client.web3.eth.syncing = synced_status
        self.assertFalse(self.client.is_synchronized())
        time.sleep(1.5 * Client.SYNC_CHECK_INTERVAL)
        self.client.web3.net.peerCount = 1
        self.client.web3.eth.syncing = syncing_status
        self.assertFalse(self.client.is_synchronized())
        time.sleep(1.5 * Client.SYNC_CHECK_INTERVAL)
        self.assertFalse(self.client.is_synchronized())

        self.client.web3.net.peerCount = 1
        self.client.web3.eth.syncing = synced_status
        self.assertFalse(self.client.is_synchronized())
        time.sleep(1.5 * Client.SYNC_CHECK_INTERVAL)
        self.assertFalse(self.client.is_synchronized())
        time.sleep(1.5 * Client.SYNC_CHECK_INTERVAL)
        self.assertTrue(self.client.is_synchronized())
        time.sleep(1.5 * Client.SYNC_CHECK_INTERVAL)
        self.client.web3.net.peerCount = 0
        self.client.web3.eth.syncing = synced_status
        self.assertFalse(self.client.is_synchronized())
        time.sleep(1.5 * Client.SYNC_CHECK_INTERVAL)
        self.client.web3.net.peerCount = 2
        self.client.web3.eth.syncing = synced_status
        self.assertFalse(self.client.is_synchronized())
        time.sleep(1.5 * Client.SYNC_CHECK_INTERVAL)
        self.assertTrue(self.client.is_synchronized())
        time.sleep(1.5 * Client.SYNC_CHECK_INTERVAL)
        self.client.web3.net.peerCount = 2
        self.client.web3.eth.syncing = syncing_status
        self.assertFalse(self.client.is_synchronized())
        Client.SYNC_CHECK_INTERVAL = tmp
