import unittest

from golem.utils import privkeytoaddr


class UtilsTest(unittest.TestCase):
    def test_privkey_to_checksum_address(self):
        eth_address = privkeytoaddr(
            b'call me highway call me conduit ')
        self.assertEqual(
            eth_address, '0xE6e819FA910f150800C91D218DFAD0C810F990F0')

    def test_privkey_to_checksum_address_fail(self):
        with self.assertRaises(ValueError):
            privkeytoaddr(
                b'call me what you will i was there when i was required'
            )
