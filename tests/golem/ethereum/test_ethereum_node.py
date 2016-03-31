import logging
import platform
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

    @unittest.skipIf(platform.system() == 'Windows', 'On Windows killing is hard')
    def test_full_node_remotely(self):
        args = ['python', '-m', 'golem.ethereum.node']
        proc = subprocess.Popen(args, bufsize=1,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)

        # Read first 6 lines searching for "started".
        started = False
        for _ in range(6):
            log = proc.stdout.readline()
            if "started" in log:
                started = True
                break
        assert started, "No 'started' word in logs"

        assert proc.returncode is None
        proc.send_signal(signal.SIGTERM)
        proc.wait()
        log = proc.stdout.read()
        assert "terminated" in log
        assert proc.returncode is 0
