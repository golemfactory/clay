import logging
import signal
import subprocess
import unittest

from golem.ethereum.node import FullNode


class EthereumClientTest(unittest.TestCase):
    def setUp(self):
        # Show information about Ethereum node starting and terminating.
        logging.basicConfig(level=logging.INFO)

    def test_full_node(self):
        n = FullNode()
        n.proc.stop()

    def test_full_node_remotely(self):
        args = ['python', '-m', 'golem.ethereum.node']
        proc = subprocess.Popen(args, bufsize=1, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        # while proc.stdout.read(1):
        #     time.sleep(0.1)

        start_log = proc.stdout.readline()
        assert "started" in start_log
        assert proc.returncode is None
        proc.send_signal(signal.SIGINT)
        proc.wait()
        log = proc.stdout.read()
        assert "terminated" in log
        assert proc.returncode is 0
