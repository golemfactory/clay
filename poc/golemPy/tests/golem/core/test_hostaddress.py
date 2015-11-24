import unittest
from golem.core.hostaddress import get_host_address


class TestHostAddress(unittest.TestCase):
    def testGetHostAddress(self):
        self.assertGreater(len(get_host_address('127.0.0.1')), 0)

    @unittest.skip("Find network testing framework")
    def testGetHostAddress2(self):
        self.assertEqual(get_host_address('10.30.100.100'), '10.30.10.216')
        self.assertEqual(get_host_address('10.30.10.217'), '10.30.10.216')
