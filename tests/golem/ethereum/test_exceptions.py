from unittest import TestCase

from ethereum.utils import denoms

from golem.ethereum.exceptions import NotEnoughFunds


class TestNotEnoughFunds(TestCase):
    def test_exception(self):
        try:
            raise NotEnoughFunds(10 * denoms.ether, 2 * denoms.ether)
        except NotEnoughFunds as err:
            expected_str = "Not enough GNT available. Required: 10.000000, " \
                           "available: 2.000000"
            assert expected_str in str(err)
