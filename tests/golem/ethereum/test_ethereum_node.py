import unittest
from distutils.version import StrictVersion
from os import path

from mock import patch, Mock

from golem.ethereum.node import log, NodeProcess, \
    FALLBACK_NODE_LIST, get_public_nodes
from golem.testutils import PEP8MixIn, TempDirFixture
from golem.tools.assertlogs import LogTestCase


class MockPopen(Mock):
    def communicate(self):
        return "Version: 1.6.2", Mock()


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

    def test_fetched_public_nodes(self):
        class Wrapper:
            @staticmethod
            def json():
                return FALLBACK_NODE_LIST

        with patch('requests.get', lambda *_: Wrapper):
            assert get_public_nodes() is FALLBACK_NODE_LIST

    def test_builtin_public_nodes(self):
        with patch('requests.get', lambda *_: None):
            public_nodes = get_public_nodes()

        assert public_nodes is not FALLBACK_NODE_LIST
        assert all(n in FALLBACK_NODE_LIST for n in public_nodes)
