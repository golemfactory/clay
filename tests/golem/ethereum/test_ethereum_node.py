from os import urandom, path
import requests
import unittest
import unittest.mock as mock

from golem.ethereum.node import log, NodeProcess, tETH_faucet_donate
from golem.testutils import PEP8MixIn, TempDirFixture
from golem.tools.assertlogs import LogTestCase
from golem.utils import encode_hex


class MockPopen(mock.Mock):
    def communicate(self):
        return "Version: 1.6.2", mock.Mock()


class RopstenFaucetTest(unittest.TestCase, PEP8MixIn):
    PEP8_FILES = ["golem/ethereum/node.py"]

    @mock.patch('requests.get')
    def test_error_code(self, get):
        addr = urandom(20)
        response = mock.Mock(spec=requests.Response)
        response.status_code = 500
        get.return_value = response
        assert tETH_faucet_donate(addr) is False

    @mock.patch('requests.get')
    def test_error_msg(self, get):
        addr = urandom(20)
        response = mock.Mock(spec=requests.Response)
        response.status_code = 200
        response.json.return_value = {'paydate': 0, 'message': "Ooops!"}
        get.return_value = response
        assert tETH_faucet_donate(addr) is False

    @mock.patch('requests.get')
    def test_success(self, get):
        addr = urandom(20)
        response = mock.Mock(spec=requests.Response)
        response.status_code = 200
        response.json.return_value = {'paydate': 1486605259,
                                      'amount': 999999999999999}
        get.return_value = response
        assert tETH_faucet_donate(addr) is True
        assert get.call_count == 1
        assert encode_hex(addr)[2:] in get.call_args[0][0]


class EthereumNodeTest(TempDirFixture, LogTestCase):
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
        with self.assertLogs(log, level="INFO") as l:
            np.start(port)
            assert any("--port=8182" in log for log in l.output)
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

    def test_geth_version_check(self):
        min = NodeProcess.MIN_GETH_VERSION
        max = NodeProcess.MAX_GETH_VERSION
        NodeProcess.MIN_GETH_VERSION = "0.1.0"
        NodeProcess.MAX_GETH_VERSION = "0.2.0"
        with self.assertRaises(OSError):
            NodeProcess(self.tempdir)
        NodeProcess.MIN_GETH_VERSION = min
        NodeProcess.MAX_GETH_VERSION = max
