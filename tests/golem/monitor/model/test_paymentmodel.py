from random import Random
import unittest.mock as mock
import uuid

from pydispatch import dispatcher

from golem.monitor.model.paymentmodel import ExpenditureModel, IncomeModel
from golem.monitor.test_helper import MonitorTestBaseClass

random = Random(__name__)


class TestExpenditureModel(MonitorTestBaseClass):

    def setUp(self):
        super().setUp()
        self.monitor.config['SEND_PAYMENT_INFO'] = True

    def test_channel(self):
        addr = str(uuid.UUID(int=random.getrandbits(128)))
        value = random.randint(1, 10 ** 20)

        with mock.patch('golem.monitor.monitor.SenderThread.send') as send:
            dispatcher.send(
                signal='golem.monitor',
                event='payment',
                addr=addr,
                value=value
            )

            send.assert_called_once()
            result = send.call_args[0][0]
            self.assertIsInstance(result, ExpenditureModel)
            self.assertEqual(result.type, 'Expense')
            self.assertEqual(result.addr, addr)
            self.assertEqual(result.value, value)


class TestIncomeModel(MonitorTestBaseClass):

    def setUp(self):
        super().setUp()
        self.monitor.config['SEND_PAYMENT_INFO'] = True

    def test_channel(self):
        addr = str(uuid.UUID(int=random.getrandbits(128)))
        value = random.randint(1, 10 ** 20)

        with mock.patch('golem.monitor.monitor.SenderThread.send') as send:
            dispatcher.send(
                signal='golem.monitor',
                event='income',
                addr=addr,
                value=value
            )

            send.assert_called_once()
            result = send.call_args[0][0]
            self.assertIsInstance(result, IncomeModel)
            self.assertEqual(result.type, 'Income')
            self.assertEqual(result.addr, addr)
            self.assertEqual(result.value, value)
