from unittest import TestCase

from ethereum.utils import denoms

from golem.ethereum.exceptions import NotEnoughFunds, MissingFunds


class TestNotEnoughFunds(TestCase):
    def test_error_message_single_currency(self):
        try:
            raise NotEnoughFunds.single_currency(
                required=5 * denoms.ether,
                available=1 * denoms.ether,
                currency='GNT'
            )
        except NotEnoughFunds as err:
            expected = f'Not enough funds available.\n' \
                f'Required GNT: 5.000000, available: 1.000000\n'
            self.assertIn(str(err), expected)

    def test_error_message_multiple_currencies(self):
        missing_funds = [
            MissingFunds(
                required=5 * denoms.ether,
                available=1 * denoms.ether,
                currency='ETH'
            ),
            MissingFunds(
                required=1 * denoms.ether,
                available=0,
                currency='GNT'
            )
        ]

        try:
            raise NotEnoughFunds(missing_funds)
        except NotEnoughFunds as err:
            expected = f'Not enough funds available.\n' \
                f'Required ETH: 5.000000, available: 1.000000\n' \
                f'Required GNT: 1.000000, available: 0.000000\n'
            self.assertIn(str(err), expected)

    def test_error_to_dict(self):
        missing_funds = [
            MissingFunds(
                required=5 * denoms.ether,
                available=1 * denoms.ether,
                currency='ETH'
            ),
            MissingFunds(
                required=1 * denoms.ether,
                available=0,
                currency='GNT'
            )
        ]

        try:
            raise NotEnoughFunds(missing_funds)
        except NotEnoughFunds as err:
            err_dict = err.to_dict()

            self.assertEqual(err_dict['error_type'], 'NotEnoughFunds')
            for i in range(2):
                self.assertEqual(err_dict['error_details']['missing_funds'][i],
                                 missing_funds[i]._asdict())
