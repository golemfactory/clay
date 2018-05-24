from random import Random
from unittest import TestCase
from unittest.mock import patch, MagicMock

import pytest

from golem.task.masking import Mask
from golem.task.taskbase import Task


class TestMask(TestCase):

    NETWORK_SIZE = 1024

    def setUp(self):
        self.random = Random(__name__)

    def _get_test_key(self):
        return self.random.getrandbits(Mask.MASK_LEN)\
            .to_bytes(Mask.KEY_SIZE, 'big', signed=False)

    def _get_test_network(self):
        return (self._get_test_key() for _ in range(self.NETWORK_SIZE))

    def test_wrong_bits_num(self):
        with self.assertRaises(AssertionError):
            Mask(num_bits=-1)
        with self.assertRaises(AssertionError):
            Mask(num_bits=Mask.MASK_LEN + 1)

    @patch('golem.task.masking.random', new=Random(__name__))
    def test_bits_num(self):
        for i in range(Mask.MASK_LEN):
            mask = Mask(num_bits=i)
            self.assertEqual(mask.num_bits, i)

    @patch('golem.task.masking.random', new=Random(__name__))
    def test_to_bin(self):
        for i in range(Mask.MASK_LEN):
            bin_repr = Mask(i).to_bin()
            bits_num = sum(x == '1' for x in bin_repr)
            self.assertEqual(bits_num, i)

    @patch.object(Mask, 'KEY_SIZE', new=4)
    @patch('golem.task.masking.random')
    def test_to_bytes(self, random):
        random.sample.return_value = range(8)
        self.assertEqual(Mask(8).to_bytes(), b'\x00\x00\x00\xff')
        random.sample.return_value = [10]
        self.assertEqual(Mask(1).to_bytes(), b'\x00\x00\x04\x00')

    @patch('golem.task.masking.random')
    def test_to_int(self, random):
        random.sample.return_value = range(8)
        self.assertEqual(Mask(8).to_int(), 255)
        random.sample.return_value = [10]
        self.assertEqual(Mask(1).to_int(), 1024)

    @patch('golem.task.masking.random', new=Random(__name__))
    def test_increase(self):
        mask = Mask(0)
        for i in range(Mask.MASK_LEN):
            self.assertEqual(mask.num_bits, i)
            mask.increase()

    @patch('golem.task.masking.random', new=Random(__name__))
    def test_decrease(self):
        mask = Mask(Mask.MASK_LEN)
        for i in range(Mask.MASK_LEN):
            self.assertEqual(mask.num_bits, Mask.MASK_LEN - i)
            mask.decrease()

    @patch('golem.task.masking.get_network_size', return_value=NETWORK_SIZE)
    def test_get_mask_for_task(self, _):
        task = MagicMock(spec=Task)

        def _check(num_subtasks, exp_num_bits):
            task.get_total_tasks.return_value = num_subtasks
            mask = Mask.get_mask_for_task(task)
            self.assertEqual(mask.num_bits, exp_num_bits)

        _check(1, 10)    # 1024 / 2**10 == 1
        _check(16, 6)    # 1024 / 2**6  == 16
        _check(80, 3)    # 1024 / 2**3 > 80 > 1024 / 2**4
        _check(5000, 0)  # 5000 > 1024 / 2 ** 0

    @pytest.mark.slow
    @patch('golem.task.masking.random', new=Random(__name__))
    @patch('golem.task.masking.get_network_size', return_value=NETWORK_SIZE)
    def test_apply(self, _):
        def _check(num_bits, exp_num_nodes):
            mask = Mask(num_bits)
            avg_nodes = sum(
                sum(mask.apply(addr) for addr in self._get_test_network())
                for _ in range(1000)) / 1000
            self.assertAlmostEqual(avg_nodes, exp_num_nodes, delta=1)

        _check(3, 128)
        _check(5, 32)
        _check(7, 8)
