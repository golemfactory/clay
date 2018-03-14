from unittest import TestCase

from golem.transactions.ethereum.exceptions import NotEnoughFunds


class TestNotEnoughFunds(TestCase):
    def test_exception(self):
        try:
            raise NotEnoughFunds(10, 2)
        except NotEnoughFunds as err:
            expected_str = "Not enough GNT available. Required: 10, " \
                           "available: 2"
            assert expected_str in str(err)
