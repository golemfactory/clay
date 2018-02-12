import logging
from ethereum.transactions import Transaction
from ethereum.utils import zpad
from os import path

from mock import patch
from web3 import Web3, IPCProvider

from golem.ethereum.node import log, NodeProcess
from golem.testutils import PEP8MixIn, TempDirFixture
from golem.tools.assertlogs import LogTestCase
from golem.utils import encode_hex
from golem_sci.client import Client


class EthereumNodeTest(TempDirFixture, LogTestCase, PEP8MixIn):
    PEP8_FILES = ["golem/ethereum/node.py"]

    def test_ethereum_node(self):
        np = NodeProcess(self.tempdir)
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
        with self.assertLogs(log, level="INFO") as logs:
            np.start(port)
            assert any("--port=8182" in log for log in logs.output)
        assert np.is_running() is True
        np.stop()
        assert np.is_running() is False

    def test_ethereum_node_reuse(self):
        np = NodeProcess(self.tempdir)
        np.start()

        # Reuse but with different directory
        ndir = path.join(self.tempdir, "ndir")
        np1 = NodeProcess(ndir)
        np1.start()
        assert np.is_running() is True
        assert np1.is_running() is True
        np.stop()
        np1.stop()


class EthereumClientNodeTest(TempDirFixture):
    def setUp(self):
        super().setUp()
        # Show information about Ethereum node starting and terminating.
        logging.basicConfig(level=logging.INFO)
        self.node = NodeProcess(self.tempdir)
        ipc_path = self.node.start()
        web3 = Web3(IPCProvider(ipc_path))
        self.client = Client(web3)

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
