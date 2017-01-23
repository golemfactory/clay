import logging
import platform
import signal
import subprocess
import unittest

from golem.ethereum.node import FullNode, Faucet, NodeProcess
from golem.ethereum import Client
from golem.testutils import TempDirFixture

from ethereum.utils import denoms


class EthereumClientTest(unittest.TestCase):
    def setUp(self):
        # Show information about Ethereum node starting and terminating.
        logging.basicConfig(level=logging.INFO)

    def test_full_node(self):
        n = FullNode()
        assert n.is_running() == True
        n.stop()
        assert n.is_running() == False

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


class EthereumFaucetTest(TempDirFixture):
    def setUp(self):
        super(EthereumFaucetTest, self).setUp()
        self.n = FullNode()
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
