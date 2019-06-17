import datetime
from unittest import TestCase, mock

from golem import model
from golem.ethereum.transactionsystem import TransactionSystem
from golem.rpc.api.ethereum_ import ETSProvider


class TestEthereum(TestCase):
    def setUp(self):
        self.ets = mock.Mock(spec_set=TransactionSystem)
        self.ets_provider = ETSProvider(self.ets)

    def test_get_gas_price(self):
        test_gas_price = 1234
        test_price_limit = 12345
        self.ets.gas_price = test_gas_price
        self.ets.gas_price_limit = test_price_limit

        result = self.ets_provider.get_gas_price()

        self.assertEqual(result["current_gas_price"], str(test_gas_price))
        self.assertEqual(result["gas_price_limit"], str(test_price_limit))

    def test_one(self):
        tx_hash = \
            '0x5e9880b3e9349b609917014690c7a0afcdec6dbbfbef3812b27b60d246ca10ae'
        value = 31337
        ts = 1514761200.0
        dt = datetime.datetime.fromtimestamp(
            ts,
            tz=datetime.timezone.utc,
        )
        deposit_payment = mock.Mock(spec_set=model.WalletOperation)
        deposit_payment.amount = value
        deposit_payment.tx_hash = tx_hash
        deposit_payment.created_date = dt
        deposit_payment.modified_date = dt
        deposit_payment.gas_cost = 0
        deposit_payment.status = model.WalletOperation.STATUS.awaiting
        self.ets.get_deposit_payments_list.return_value = [deposit_payment]

        expected = [
            {
                'created': ts,
                'modified': ts,
                'fee': '0',
                'status': 'awaiting',
                'transaction': tx_hash,
                'value': str(value),
            },
        ]
        self.assertEqual(
            expected,
            self.ets_provider.get_deposit_payments_list(),
        )
