import os

from unittest import mock, TestCase

from ethereum.utils import privtoaddr
from eth_utils import encode_hex

from golem_messages import message
from golem_messages.cryptography import ECCx

from golem.network.concent import helpers


class HelpersTest(TestCase):
    def test_self_payment(self):
        privkey = os.urandom(32)
        addr = privtoaddr(privkey)

        ecc = ECCx(privkey)
        ecc.verify = mock.Mock()
        msg = mock.Mock()
        msg.task_to_compute.provider_ethereum_address = encode_hex(addr)

        res = helpers.process_report_computed_task_no_time_check(msg, ecc, )
        self.assertIsInstance(res, message.tasks.RejectReportComputedTask)

    def test_payment_to_zero(self):
        ecc = mock.Mock()
        ecc.get_privkey.return_value = os.urandom(32)
        msg = mock.Mock()
        msg.task_to_compute.provider_ethereum_address = '0x' + 40 * '0'

        res = helpers.process_report_computed_task_no_time_check(msg, ecc, )
        self.assertIsInstance(res, message.tasks.RejectReportComputedTask)
