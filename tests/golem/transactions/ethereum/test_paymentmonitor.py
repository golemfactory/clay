import mock
import time
import unittest
from copy import deepcopy
from os import urandom

from golem.ethereum import Client
from golem.ethereum.paymentmonitor import PaymentMonitor, PaymentStatus


def wait_for(condition, timeout, step=0.1):
    for _ in xrange(int(timeout / step)):
        if condition():
            return True
        time.sleep(step)
    return False


class PaymentMonitorTest(unittest.TestCase):

    def setUp(self):
        self.addr = urandom(20)
        self.client = mock.MagicMock(spec=Client)
        self.pm = PaymentMonitor(self.client, self.addr)

    def test_process_incoming_payments(self):
        self.pm.process_incoming_payments()
        assert not self.pm.get_incoming_payments()
        assert self.client.new_filter.call_count == 1

        payee1 = urandom(20)
        payee2 = urandom(20)
        v1 = 1234 * 10**16
        v2 = 4567 * 10**17

        p1 = {
            'topics': [
                'ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef',
                '0x' + 24*'0' + payee1.encode('hex'),
                '0x' + 24*'0' + self.addr.encode('hex'),
            ],
            'data': '0x{:x}'.format(v1),
            'blockNumber': '0x' + urandom(3).encode('hex'),
            'blockHash': '0x' + urandom(32).encode('hex'),
            'transactionHash': '0x' + urandom(32).encode('hex')
        }
        p2 = deepcopy(p1)
        p2['topics'][1] = '0x' + 24*'0' + payee2.encode('hex')
        p2['data'] = '0x{:x}'.format(v2)
        self.client.get_filter_changes.return_value = [p1, p2]
        self.pm.process_incoming_payments()
        payment = self.pm.get_incoming_payments()[0]
        assert payment.status == PaymentStatus.confirmed
        assert payment.value == v1
        assert payment.payer == payee1
        payment = self.pm.get_incoming_payments()[1]
        assert payment.status == PaymentStatus.confirmed
        assert payment.value == v2
        assert payment.payer == payee2
