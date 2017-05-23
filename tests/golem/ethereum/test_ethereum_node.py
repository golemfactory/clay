import unittest
from os import urandom

import requests
from mock import patch, Mock

from golem.ethereum.node import NodeProcess, ropsten_faucet_donate
from golem.testutils import TempDirFixture


class MockPopen(Mock):
    def communicate(self):
        return "Version: 1.6.2", Mock()


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
        response.json.return_value = {'paydate': 1486605259,
                                      'amount': 999999999999999}
        get.return_value = response
        assert ropsten_faucet_donate(addr) is True
        assert get.call_count == 1
        assert addr.encode('hex') in get.call_args[0][0]


class EthereumNodeTest(TempDirFixture):
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

    @unittest.skip("Ethereum node sharing not supported")
    def test_ethereum_node_reuse(self):
        np = NodeProcess(self.tempdir)
        np.start()
        np1 = NodeProcess(self.tempdir)
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
