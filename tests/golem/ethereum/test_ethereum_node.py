import unittest
import requests
from os import urandom
from mock import patch, Mock

from golem.ethereum.node import NodeProcess, ropsten_faucet_donate, is_geth_listening


class RopstenFaucetTest(unittest.TestCase):
    @patch('requests.get')
    def test_error_code(self, get):
        addr = urandom(20)
        response = Mock(spec=requests.Response)
        response.status_code = 500
        get.return_value = response
        assert ropsten_faucet_donate(addr) is False

    @patch('requests.get')
    def test_error_msg(self, get):
        addr = urandom(20)
        response = Mock(spec=requests.Response)
        response.status_code = 200
        response.json.return_value = {'paydate': 0, 'message': "Ooops!"}
        get.return_value = response
        assert ropsten_faucet_donate(addr) is False

    @patch('requests.get')
    def test_success(self, get):
        addr = urandom(20)
        response = Mock(spec=requests.Response)
        response.status_code = 200
        response.json.return_value = {'paydate': 1486605259, 'amount': 999999999999999}
        get.return_value = response
        assert ropsten_faucet_donate(addr) is True
        assert get.call_count == 1
        addr.encode('hex') in get.call_args[0][0]


class EthereumNodeTest(unittest.TestCase):
    @unittest.skipIf(is_geth_listening(NodeProcess.testnet),
                     "geth is already running; skipping starting and stopping tests")
    def test_ethereum_node(self):
        np = NodeProcess()
        assert np.is_running() is False
        np.start()
        assert np.is_running() is True
        with self.assertRaises(RuntimeError):
            np.start()
        assert np.is_running() is True
        np.stop()
        assert np.is_running() is False

    def test_geth_version_check(self):
        min = NodeProcess.MIN_GETH_VERSION
        max = NodeProcess.MAX_GETH_VERSION
        NodeProcess.MIN_GETH_VERSION = "0.1.0"
        NodeProcess.MAX_GETH_VERSION = "0.2.0"
        with self.assertRaises(OSError):
            NodeProcess()
        NodeProcess.MIN_GETH_VERSION = min
        NodeProcess.MAX_GETH_VERSION = max
