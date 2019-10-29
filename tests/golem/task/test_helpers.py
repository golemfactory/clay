import unittest

from ethereum.utils import denoms

from golem.task.helpers import calculate_max_usage, calculate_subtask_payment

PWEI = denoms.finney
HOUR = 3600


class MaxUsageTest(unittest.TestCase):
    def test_calculate_max_usage(self):
        budget = 10 * PWEI  # 0.01 GNT
        price_per_hour = 100 * PWEI  # 0.1 GNT
        self.assertEqual(calculate_max_usage(budget, price_per_hour), 360)

    def test_uneven_above(self):
        budget = 10 * PWEI  # 0.01 GNT
        price_per_hour = 70 * PWEI  # 0.07 GNT
        self.assertEqual(calculate_max_usage(budget, price_per_hour), 515)

    def test_uneven_below(self):
        budget = 10 * PWEI  # 0.01 GNT
        price_per_hour = 130 * PWEI  # 0.13 GNT
        self.assertEqual(calculate_max_usage(budget, price_per_hour), 277)


class SubtaskAmountTest(unittest.TestCase):
    def test_calculate_subtask_amount(self):
        price_per_hour = 100 * PWEI  # 0.1 GNT
        calculation_time = 360
        self.assertEqual(
            calculate_subtask_payment(price_per_hour, calculation_time),
            10 * PWEI  # 0.01 GNT
        )
