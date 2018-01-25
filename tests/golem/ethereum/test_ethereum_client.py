import time
from unittest import mock

from golem.ethereum import Client
from golem.testutils import TempDirFixture

SYNC_TEST_INTERVAL = 0.01


class EthereumClientTest(TempDirFixture):
    def setUp(self):
        super().setUp()
        self.web3 = mock.Mock()
        self.client = Client(self.web3)

    def check_synchronized(self):
        assert not self.client.is_synchronized()
        self.web3.net.peerCount = 1
        self.web3.eth.syncing = {
            "currentBlock": 1,
            "highestBlock": 1,
        }
        self.assertFalse(self.client.is_synchronized())
        tmp = Client.SYNC_CHECK_INTERVAL = SYNC_TEST_INTERVAL
        time.sleep(1.5 * self.client.SYNC_CHECK_INTERVAL)
        self.assertFalse(self.client.is_synchronized())
        time.sleep(1.5 * self.client.SYNC_CHECK_INTERVAL)
        self.assertTrue(self.client.is_synchronized())
        Client.SYNC_CHECK_INTERVAL = tmp

    def test_synchronized2(self):
        self.check_synchronized()

    def test_wait_until_synchronized(self):
        Client.SYNC_CHECK_INTERVAL = SYNC_TEST_INTERVAL
        self.web3.net.peerCount = 1
        self.web3.eth.syncing = {
            "currentBlock": 1,
            "highestBlock": 1,
        }
        self.assertTrue(self.client.wait_until_synchronized())

    def test_synchronized(self):
        tmp = Client.SYNC_CHECK_INTERVAL
        Client.SYNC_CHECK_INTERVAL = SYNC_TEST_INTERVAL
        syncing_status = {'startingBlock': '0x384',
                          'currentBlock': '0x386',
                          'highestBlock': '0x454'}
        combinations = ((0, False),
                        (0, syncing_status),
                        (1, False),
                        (1, syncing_status),
                        (65, syncing_status),
                        (65, False))

        self.web3.eth.syncing = {
            'currentBlock': 123,
            'highestBlock': 1234,
        }
        self.web3.eth.getBlock.return_value = {"timestamp": time.time()}

        for c in combinations:
            print("Subtest {}".format(c))
            # Allow reseting the status.
            time.sleep(1.5 * Client.SYNC_CHECK_INTERVAL)
            self.web3.net.peerCount = 0
            self.assertFalse(self.client.is_synchronized())
            time.sleep(1.5 * Client.SYNC_CHECK_INTERVAL)
            self.web3.net.peerCount = c[0]
            self.web3.eth.syncing = c[1]
            # First time is always no.a
            self.assertFalse(self.client.is_synchronized())
            time.sleep(1.5 * Client.SYNC_CHECK_INTERVAL)
            self.assertTrue(self.client.is_synchronized() == (c[0] and not c[1]))  # noqa
        Client.SYNC_CHECK_INTERVAL = tmp

    def test_synchronized_unstable(self):
        tmp = Client.SYNC_CHECK_INTERVAL
        Client.SYNC_CHECK_INTERVAL = SYNC_TEST_INTERVAL
        syncing_status = {
            'startingBlock': '0x0',
            'currentBlock': '0x1',
            'highestBlock': '0x4096',
        }
        synced_status = {
            'startingBlock': '0x0',
            'currentBlock': '0x1',
            'highestBlock': '0x1',
        }

        self.web3.net.peerCount = 1
        self.web3.eth.syncing = synced_status
        self.assertFalse(self.client.is_synchronized())
        time.sleep(1.5 * Client.SYNC_CHECK_INTERVAL)
        self.web3.net.peerCount = 1
        self.web3.eth.syncing = syncing_status
        self.assertFalse(self.client.is_synchronized())
        time.sleep(1.5 * Client.SYNC_CHECK_INTERVAL)
        self.assertFalse(self.client.is_synchronized())

        self.web3.net.peerCount = 1
        self.web3.eth.syncing = synced_status
        self.assertFalse(self.client.is_synchronized())
        time.sleep(1.5 * Client.SYNC_CHECK_INTERVAL)
        self.assertFalse(self.client.is_synchronized())
        time.sleep(1.5 * Client.SYNC_CHECK_INTERVAL)
        self.assertTrue(self.client.is_synchronized())
        time.sleep(1.5 * Client.SYNC_CHECK_INTERVAL)
        self.web3.net.peerCount = 0
        self.web3.eth.syncing = synced_status
        self.assertFalse(self.client.is_synchronized())
        time.sleep(1.5 * Client.SYNC_CHECK_INTERVAL)
        self.web3.net.peerCount = 2
        self.web3.eth.syncing = synced_status
        self.assertFalse(self.client.is_synchronized())
        time.sleep(1.5 * Client.SYNC_CHECK_INTERVAL)
        self.assertTrue(self.client.is_synchronized())
        time.sleep(1.5 * Client.SYNC_CHECK_INTERVAL)
        self.web3.net.peerCount = 2
        self.web3.eth.syncing = syncing_status
        self.assertFalse(self.client.is_synchronized())
        Client.SYNC_CHECK_INTERVAL = tmp
