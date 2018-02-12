import logging
import unittest
from distutils.version import StrictVersion
from ethereum.transactions import Transaction
from ethereum.utils import zpad
from os import path

from mock import patch, Mock

from golem.ethereum.node import log, NodeProcess, \
    NODE_LIST, get_public_nodes
from golem.testutils import PEP8MixIn, TempDirFixture
from golem.tools.assertlogs import LogTestCase
from golem.utils import encode_hex
from golem_sci.client import Client


class EthereumNodeTest(TempDirFixture, LogTestCase, PEP8MixIn):
    PEP8_FILES = ["golem/ethereum/node.py"]

    def test_ethereum_node(self):
        np = NodeProcess(self.tempdir, start_node=True)
        assert np.is_running() is False
        np.start()
        assert np.is_running() is True
        with self.assertRaises(RuntimeError):
            np.start()
        assert np.is_running() is True
        np.stop()
        assert np.is_running() is False

        # Test different port option
        port = 8182
        with self.assertLogs(log, level="INFO") as l:
            np.start(port)
            assert any("--port=8182" in log for log in l.output)
        assert np.is_running() is True
        np.stop()
        assert np.is_running() is False

    def test_ethereum_node_reuse(self):
        np = NodeProcess(self.tempdir, start_node=True)
        np.start()

        # Reuse but with different directory
        ndir = path.join(self.tempdir, "ndir")
        np1 = NodeProcess(ndir, start_node=True)
        np1.start()
        assert np.is_running() is True
        assert np1.is_running() is True
        np.stop()
        np1.stop()

    @patch('golem.ethereum.node.NodeProcess.MIN_GETH_VERSION',
           StrictVersion('0.1.0'))
    @patch('golem.ethereum.node.NodeProcess.MAX_GETH_VERSION',
           StrictVersion('0.2.0'))
    def test_geth_version_check(self):
        node = NodeProcess(self.tempdir, start_node=True)
        with self.assertRaises(OSError):
            node.start()

    def test_start_timed_out(self):
        provider = Mock()
        port = 3000

        np = NodeProcess(self.tempdir)
        np.start = Mock()
        np.start_node = True

        with self.assertRaises(OSError):
            np._start_timed_out(provider, port)
        assert not np.start.called

        np.start_node = False
        np._start_timed_out(provider, port)
        assert np.start.called


class TestPublicNodeList(unittest.TestCase):

    def test_builtin_public_nodes(self):
        with patch('requests.get', lambda *_: None):
            public_nodes = get_public_nodes()

        assert public_nodes is not NODE_LIST
        assert all(n in NODE_LIST for n in public_nodes)


class EthereumClientNodeTest(TempDirFixture):
    def setUp(self):
        super().setUp()
        # Show information about Ethereum node starting and terminating.
        logging.basicConfig(level=logging.INFO)
        self.node = NodeProcess(self.tempdir, start_node=True)
        self.node.start()
        self.client = Client(self.node.web3)

    def tearDown(self):
        self.node.stop()
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
        with patch.object(eth, 'getBalance', side_effect=ValueError):
            b = client.get_balance(hex_addr)
        assert b is None

    def test_send_raw_transaction(self):
        client = self.client
        with self.assertRaises(ValueError):
            client.send("fake data")

    def test_send_transaction(self):
        client = self.client
        addr = b'\xff' * 20
        priv = b'\xee' * 32
        tx = Transaction(1, 20 * 10**9, 21000, to=addr, value=0, data=b'')
        tx.sign(priv)
        with self.assertRaisesRegex(ValueError, "[Ii]nsufficient funds"):
            client.send(tx)

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
