from random import Random
from unittest import TestCase
from unittest.mock import patch

import pytest

from golem.task.masking import Mask


class TestMask(TestCase):

    NETWORK_SIZE = 1024

    def setUp(self):
        self.random = Random(__name__)

    def _get_test_key(self):
        return self.random.getrandbits(Mask.MASK_LEN)\
            .to_bytes(Mask.MASK_LEN // 8, 'big', signed=False)

    def _get_test_network(self):
        return (self._get_test_key() for _ in range(self.NETWORK_SIZE))

    def test_generate_negative_bits_num(self):
        with self.assertRaises(ValueError):
            Mask.generate(num_bits=-1)

    def test_generate_num_bits_above_limit(self):
        mask = Mask.generate(num_bits=Mask.MASK_LEN + 1)
        self.assertEqual(mask.num_bits, Mask.MASK_LEN)

    @patch('golem.task.masking.random', new=Random(__name__))
    def test_bits_num(self):
        for i in range(Mask.MASK_LEN):
            mask = Mask.generate(num_bits=i)
            self.assertEqual(mask.num_bits, i)

    @patch('golem.task.masking.random', new=Random(__name__))
    def test_to_bin(self):
        for i in range(Mask.MASK_LEN):
            bin_repr = Mask.generate(i).to_bin()
            bits_num = sum(x == '1' for x in bin_repr)
            self.assertEqual(bits_num, i)

    @patch.object(Mask, 'MASK_BYTES', new=4)
    @patch('golem.task.masking.random')
    def test_to_bytes(self, random):
        random.sample.return_value = range(8)
        self.assertEqual(Mask.generate(8).to_bytes(), b'\x00\x00\x00\xff')
        random.sample.return_value = [10]
        self.assertEqual(Mask.generate(1).to_bytes(), b'\x00\x00\x04\x00')

    @patch('golem.task.masking.random')
    def test_to_int(self, random):
        random.sample.return_value = range(8)
        self.assertEqual(Mask.generate(8).to_int(), 255)
        random.sample.return_value = [10]
        self.assertEqual(Mask.generate(1).to_int(), 1024)

    @patch('golem.task.masking.random', new=Random(__name__))
    def test_increase(self):
        mask = Mask()
        for i in range(Mask.MASK_LEN):
            self.assertEqual(mask.num_bits, i)
            mask.increase()

    def test_increase_above_limit(self):
        mask = Mask()
        mask.increase(Mask.MASK_LEN + 1)
        self.assertEqual(mask.num_bits, Mask.MASK_LEN)

    def test_increase_below_limit(self):
        mask = Mask()
        with self.assertRaises(ValueError):
            mask.increase(-1)

    @patch('golem.task.masking.random', new=Random(__name__))
    def test_decrease(self):
        mask = Mask(b'\xff' * Mask.MASK_BYTES)
        for i in range(Mask.MASK_LEN):
            self.assertEqual(mask.num_bits, Mask.MASK_LEN - i)
            mask.decrease()

    def test_decrease_above_limit(self):
        mask = Mask(b'\xff' * Mask.MASK_BYTES)
        mask.decrease(Mask.MASK_LEN + 1)
        self.assertEqual(mask.num_bits, 0)

    def test_decrease_below_limit(self):
        mask = Mask(b'\xff' * Mask.MASK_BYTES)
        with self.assertRaises(ValueError):
            mask.decrease(-1)

    def test_get_mask_for_task_zero_network_size(self):
        mask = Mask.get_mask_for_task(10, 0)
        self.assertEqual(mask.num_bits, 0)

    def test_get_mask_for_task(self):
        def _check(num_subtasks, exp_num_bits):
            mask = Mask.get_mask_for_task(num_subtasks, self.NETWORK_SIZE)
            self.assertEqual(mask.num_bits, exp_num_bits)

        _check(1, 10)    # 1024 / 2**10 == 1
        _check(16, 6)    # 1024 / 2**6  == 16
        _check(80, 4)    # 1024 / 2**3 > 80 > 1024 / 2**4
        _check(5000, 0)  # 5000 > 1024 / 2 ** 0

    @pytest.mark.slow
    @patch('golem.task.masking.random', new=Random(__name__))
    def test_matches(self):
        def _check(num_bits, exp_num_nodes):
            mask = Mask.generate(num_bits)
            avg_nodes = sum(
                sum(mask.matches(addr) for addr in self._get_test_network())
                for _ in range(1000)) / 1000
            self.assertAlmostEqual(avg_nodes, exp_num_nodes, delta=1)

        _check(3, 128)  # 1024 / 2**3 == 128
        _check(5, 32)   # 1024 / 2**5 == 32
        _check(7, 8)    # 1024 / 2**7 == 8
