import logging
import platform
import signal
import subprocess
import unittest
import requests
from os import urandom
from mock import patch, Mock

from golem.ethereum.node import FullNode, Faucet, NodeProcess, ropsten_faucet_donate
from golem.ethereum import Client
from golem.testutils import TempDirFixture

from ethereum.utils import denoms


class EthereumClientTest(unittest.TestCase):
    def setUp(self):
        # Show information about Ethereum node starting and terminating.
        logging.basicConfig(level=logging.INFO)

    def test_full_node(self):
        n = FullNode()
        assert n.is_running() is True
        n.stop()
        assert n.is_running() is False

    @unittest.skipIf(platform.system() == 'Windows', 'On Windows killing is hard')
    def test_full_node_remotely(self):
        args = ['python', '-m', 'golem.ethereum.node']
        proc = subprocess.Popen(args, bufsize=1,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)

        # Read first 6 lines searching for "started".
        started = False
        for _ in range(20):
            log = proc.stdout.readline()
            print log
            if "started" in log:
                started = True
                break

        self.assertIsNone(proc.returncode)
        proc.send_signal(signal.SIGTERM)
        proc.wait()
        self.assertTrue(started, "No 'started' word in logs")
        log = proc.stdout.read()
        self.assertTrue("terminated" in log)
        self.assertEqual(proc.returncode, 0)


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


class EthereumFaucetTest(TempDirFixture):
    def setUp(self):
        super(EthereumFaucetTest, self).setUp()
        self.n = FullNode(run=False)
        self.eth_node = Client(datadir=self.tempdir)

    def teardown(self):
        self.n.proc.stop()

    def test_faucet_gimme_money(self):
        BANK_ADDR = "0xcfdc7367e9ece2588afe4f530a9adaa69d5eaedb"
        Faucet.gimme_money(self.eth_node, BANK_ADDR, 3 * denoms.ether)

    def test_deploy_contract(self):
        address = Faucet.deploy_contract(self.eth_node, "init code")
        assert type(address) is str
        assert len(address) == 20


class EthereumNodeTest(TempDirFixture):
    def test_ethereum_node(self):
        from os.path import join
        filename = join(self.path, "test_ethereum_node")
        open(filename, 'a').close()
        with self.assertRaises(IOError):
            NodeProcess(None, filename)
        np = NodeProcess([], self.path)
        self.assertFalse(np.is_running())
        np.start(None)
        self.assertTrue(np.is_running())
        np.stop()
        self.assertFalse(np.is_running())

        min = NodeProcess.MIN_GETH_VERSION
        max = NodeProcess.MAX_GETH_VERSION
        NodeProcess.MIN_GETH_VERSION = "0.1.0"
        NodeProcess.MAX_GETH_VERSION = "0.2.0"
        with self.assertRaises(OSError):
            NodeProcess([], self.path)
        NodeProcess.MIN_GETH_VERSION = min
        NodeProcess.MAX_GETH_VERSION = max
