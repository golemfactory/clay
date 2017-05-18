import json
import os
import unittest
from os import urandom

import requests
import sys
from mock import patch, Mock

from golem.ethereum.node import (NodeProcess, ropsten_faucet_donate,
                                 is_geth_listening, get_default_geth_path)
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
    @unittest.skipIf(is_geth_listening(NodeProcess.testnet),
                     "geth is already running; skipping start/stop tests")
    @patch('golem.ethereum.node.NodeProcess.save_static_nodes')
    def test_ethereum_node(self, *_):
        np = NodeProcess(self.tempdir)
        assert np.is_running() is False
        np.start()
        assert np.is_running() is True
        with self.assertRaises(RuntimeError):
            np.start()
        assert np.is_running() is True
        np.stop()
        assert np.is_running() is False

    @unittest.skipIf(is_geth_listening(NodeProcess.testnet),
                     "geth is already running; skipping start/stop tests")
    @patch('golem.ethereum.node.NodeProcess.save_static_nodes')
    def test_ethereum_node_reuse(self, *_):
        np = NodeProcess(self.tempdir)
        np.start()
        np1 = NodeProcess(self.tempdir)
        np1.start()
        assert np.is_running() is True
        assert np1.is_running() is True
        assert np.system_geth is False
        assert np1.system_geth is True
        np.stop()
        np1.stop()

    @patch('golem.ethereum.node.NodeProcess.save_static_nodes')
    def test_geth_version_check(self, *_):
        min = NodeProcess.MIN_GETH_VERSION
        max = NodeProcess.MAX_GETH_VERSION
        NodeProcess.MIN_GETH_VERSION = "0.1.0"
        NodeProcess.MAX_GETH_VERSION = "0.2.0"
        with self.assertRaises(OSError):
            NodeProcess(self.tempdir)
        NodeProcess.MIN_GETH_VERSION = min
        NodeProcess.MAX_GETH_VERSION = max

    @unittest.skipIf(is_geth_listening(NodeProcess.testnet),
                     "geth is already running; skipping start/stop tests")
    @patch('subprocess.Popen', return_value=MockPopen())
    @patch('web3.Web3.isConnected', return_value=True)
    @patch('golem.ethereum.node.is_geth_listening', return_value=False)
    def test_save_static_nodes(self, *_):
        data_dir_win = os.path.join(self.tempdir, '.ethereum')
        data_dir = os.path.join(data_dir_win, 'geth.ipc')

        nodes_file = Mock()
        nodes_file.return_value = nodes_file

        with patch('golem.ethereum.node.get_default_geth_path',
                   return_value=data_dir_win), \
            patch('golem.ethereum.node.is_windows',
                  return_value=True):

            np = NodeProcess(self.tempdir)
            np.start()

            nodes_path = os.path.join(data_dir_win, 'static-nodes.json')

            assert os.path.exists(data_dir_win)
            assert os.path.exists(nodes_path)
            assert json.loads(open(nodes_path).read()) == NodeProcess.BOOT_NODES

        with patch('golem.ethereum.node.get_default_geth_path',
                   return_value=data_dir), \
            patch('golem.ethereum.node.is_windows',
                  return_value=False):

            np = NodeProcess(self.tempdir)
            np.start()

            geth_dir = os.path.dirname(data_dir)
            nodes_path = os.path.join(geth_dir, 'static-nodes.json')

            assert os.path.exists(geth_dir)
            assert os.path.exists(nodes_path)
            assert json.loads(open(nodes_path).read()) == NodeProcess.BOOT_NODES


class TestDefaultGethPath(unittest.TestCase):

    def test_get_default_geth_path(self):
        with patch.object(sys, 'platform', 'darwin'):
            assert get_default_geth_path()
            assert get_default_geth_path(True)

        with patch.object(sys, 'platform', 'linux'):
            assert get_default_geth_path()
            assert get_default_geth_path(True)

        with patch.object(sys, 'platform', 'win32'):
            assert get_default_geth_path()
            assert get_default_geth_path(True)

        with patch.object(sys, 'platform', 'freebsd'):
            with self.assertRaises(ValueError):
                assert get_default_geth_path()
            with self.assertRaises(ValueError):
                assert get_default_geth_path(True)
