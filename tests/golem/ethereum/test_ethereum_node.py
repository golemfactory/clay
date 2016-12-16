import logging
import platform
import signal
import subprocess
import unittest

from golem.ethereum.node import FullNode, Faucet
from golem.ethereum import Client
from golem.testutils import TempDirFixture

from ethereum.utils import denoms


class EthereumClientTest(unittest.TestCase):
    def setUp(self):
        # Show information about Ethereum node starting and terminating.
        logging.basicConfig(level=logging.INFO)

    def test_full_node(self):
        n = FullNode()
        n.proc.stop()

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

        assert proc.returncode is None
        proc.send_signal(signal.SIGTERM)
        proc.wait()
        assert started, "No 'started' word in logs"
        log = proc.stdout.read()
        assert "terminated" in log
        assert proc.returncode is 0


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
