from random import Random
import unittest.mock as mock

from pydispatch import dispatcher

from golem.monitor.model.balancemodel import BalanceModel
from golem.monitor.test_helper import MonitorTestBaseClass

random = Random(__name__)


class TestBalanceModel(MonitorTestBaseClass):

    def test_channel(self):
        eth_balance = random.randint(1, 10 ** 20)
        gnt_balance = random.randint(1, 10 ** 20)
        gntw_balance = random.randint(1, 10 ** 20)

        with mock.patch('golem.monitor.monitor.SenderThread.send') as send:
            dispatcher.send(
                signal='golem.monitor',
                event='balance_snapshot',
                eth_balance=eth_balance,
                gnt_balance=gnt_balance,
                gntw_balance=gntw_balance
            )

            send.assert_called_once()
            result = send.call_args[0][0]
            self.assertIsInstance(result, BalanceModel)
            self.assertEqual(result.type, 'Balance')
            self.assertEqual(result.eth_balance, eth_balance)
            self.assertEqual(result.gnt_balance, gnt_balance)
            self.assertEqual(result.gntw_balance, gntw_balance)
