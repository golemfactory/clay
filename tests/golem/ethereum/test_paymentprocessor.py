import mock
import unittest

from golem.ethereum import paymentprocessor


class TestPaymentProcessor(unittest.TestCase):
    def setUp(self):
        privkey = '!\xcd!^\xfe#\x82-#!Z]b\xb4\x8ce[\n\xfbN\x18V\x8c\x1dA\xea\x8c\xe8ZO\xc9\xdb'
        self.payment_processor = paymentprocessor.PaymentProcessor(
            client=mock.MagicMock(),
            privkey=privkey
        )

    def test_eth_address(self):
        # Test with zpad
        expected = '0x000000000000000000000000e1ad9e38fc4bf20e5d4847e00e8a05170c87913f'
        self.assertEquals(expected, self.payment_processor.eth_address())

        # Test without zpad
        expected = '0xe1ad9e38fc4bf20e5d4847e00e8a05170c87913f'
        result = self.payment_processor.eth_address(zpad=False)
        self.assertEquals(expected, result)
