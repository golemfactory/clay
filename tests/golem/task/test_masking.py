from random import Random
from unittest import TestCase
from unittest.mock import patch

from golem.task import masking


class TestGenMask(TestCase):

    def setUp(self):
        self.random = Random(__name__)

    def test_gen_mask_wrong_key_size(self):
        with self.assertRaises(AssertionError):
            masking.gen_mask(bits_num=1, key_size=-1)

    def test_gen_mask_wrong_key_difficulty(self):
        with self.assertRaises(AssertionError):
            masking.gen_mask(bits_num=1, key_difficulty=-1)
        with self.assertRaises(AssertionError):
            masking.gen_mask(bits_num=1, key_size=1, key_difficulty=10)

    def test_gen_mask_wrong_bits_num(self):
        with self.assertRaises(AssertionError):
            masking.gen_mask(bits_num=-1)
        with self.assertRaises(AssertionError):
            masking.gen_mask(bits_num=10, key_size=1, key_difficulty=0)

    def test_gen_mask_leading_zeros(self):
        with patch.object(masking, 'random', new=self.random):
            for i in range(100):
                m = masking.gen_mask(bits_num=64, key_size=64, key_difficulty=i)
                bin_repr = format(m, '0512b')
                self.assertEqual(bin_repr[:i], '0' * i)

    def test_gen_mask_correct_bits_num(self):
        with patch.object(masking, 'random', new=self.random):
            for i in range(100):
                m = masking.gen_mask(bits_num=i)
                bin_repr = format(m, '0512b')
                bits_num = sum(x == '1' for x in bin_repr)
                self.assertEqual(bits_num, i)


class TestGetMaskForTask(TestCase):

    NETWORK_SIZE = 1000

    def setUp(self):
        self.random = Random(__name__)

    def _get_test_key(self, size=64, difficulty=14):
        return self.random.getrandbits(size * 8 - difficulty)\
            .to_bytes(size, 'big')

    def _get_network(self):
        return (self._get_test_key() for _ in range(self.NETWORK_SIZE))

