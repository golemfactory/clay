import unittest
from distutils.version import StrictVersion
from os import urandom, path

import requests
from mock import patch, Mock

from golem.ethereum.node import log, NodeProcess, tETH_faucet_donate, \
    FALLBACK_NODE_LIST, random_public_nodes
from golem.testutils import PEP8MixIn, TempDirFixture
from golem.tools.assertlogs import LogTestCase
from golem.utils import encode_hex


class MockPopen(Mock):
    def communicate(self):
        return "Version: 1.6.2", Mock()


class RopstenFaucetTest(unittest.TestCase, PEP8MixIn):
    PEP8_FILES = ["golem/ethereum/node.py"]

    @patch('requests.get')
    def test_error_code(self, get):
        addr = urandom(20)
        response = Mock(spec=requests.Response)
        response.status_code = 500
        get.return_value = response
        assert tETH_faucet_donate(addr) is False

    @patch('requests.get')
    def test_error_msg(self, get):
        addr = urandom(20)
        response = Mock(spec=requests.Response)
        response.status_code = 200
        response.json.return_value = {'paydate': 0, 'message': "Ooops!"}
        get.return_value = response
        assert tETH_faucet_donate(addr) is False

    @patch('requests.get')
    def test_success(self, get):
        addr = urandom(20)
        response = Mock(spec=requests.Response)
        response.status_code = 200
        response.json.return_value = {'paydate': 1486605259,
                                      'amount': 999999999999999}
        get.return_value = response
        assert tETH_faucet_donate(addr) is True
        assert get.call_count == 1
        assert encode_hex(addr)[2:] in get.call_args[0][0]


class EthereumNodeTest(TempDirFixture, LogTestCase):
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


class TestPublicNodeList(unittest.TestCase):

    def test_fetched_public_nodes(self):
        class Wrapper:
            @staticmethod
            def json():
                return FALLBACK_NODE_LIST

        with patch('requests.get', lambda *_: Wrapper):
            assert random_public_nodes() is FALLBACK_NODE_LIST

    def test_builtin_public_nodes(self):
        with patch('requests.get', lambda *_: None):
            public_nodes = random_public_nodes()

        assert public_nodes is not FALLBACK_NODE_LIST
        assert all(n in FALLBACK_NODE_LIST for n in public_nodes)
