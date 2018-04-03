from unittest import TestCase, mock
import os

from ethereum.utils import privtoaddr
from eth_utils import encode_hex
from golem_messages.cryptography import ECCx
from golem_messages import message

from golem.network.concent import helpers


class HelpersTest(TestCase):
    def test_self_payment(self):
        privkey = os.urandom(32)
        addr = privtoaddr(privkey)

        ecc = ECCx(privkey)
        ecc.verify = mock.Mock()
        msg = mock.Mock()
        msg.eth_account = encode_hex(addr)

        res = helpers.process_report_computed_task(msg, ecc, mock.Mock())
        assert isinstance(res, message.concents.RejectReportComputedTask)
