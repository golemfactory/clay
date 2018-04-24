import os

from unittest import mock, TestCase

from ethereum.utils import privtoaddr
from eth_utils import encode_hex

from golem_messages import message
from golem_messages import shortcuts as msg_shortcuts
from golem_messages.cryptography import ECCx
from golem_messages.factories.tasks import ReportComputedTaskFactory

from golem import testutils
from golem.core.keysauth import KeysAuth

from golem.network.concent import helpers


class VerifyMessageSignatureTest(testutils.TempDirFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.keys_auth = KeysAuth(
            datadir=self.tempdir,
            private_key_name='golden',
            password='friend',
        )
        self.other_keys = KeysAuth(
            datadir=self.tempdir,
            private_key_name='silver',
            password='foe',
        )

    def test_verify_ok(self):
        msg = ReportComputedTaskFactory()
        msg_dump = msg_shortcuts.dump(msg,
                                      self.keys_auth._private_key,
                                      None)
        sig_ok = helpers.verify_message_signature(
            msg_shortcuts.load(msg_dump, None, self.keys_auth.public_key),
            self.keys_auth.ecc)

        self.assertTrue(sig_ok)

    def test_verify_fail(self):
        msg = ReportComputedTaskFactory()
        msg_dump = msg_shortcuts.dump(msg,
                                      self.other_keys._private_key,
                                      None)
        sig_ok = helpers.verify_message_signature(
            msg_shortcuts.load(msg_dump, None, self.other_keys.public_key),
            self.keys_auth.ecc,
        )
        self.assertFalse(sig_ok)


class HelpersTest(TestCase):
    def test_self_payment(self):
        privkey = os.urandom(32)
        addr = privtoaddr(privkey)

        ecc = ECCx(privkey)
        ecc.verify = mock.Mock()
        msg = mock.Mock()
        msg.eth_account = encode_hex(addr)

        res = helpers.process_report_computed_task(msg, ecc, mock.Mock())
        self.assertIsInstance(res, message.tasks.RejectReportComputedTask)

    def test_payment_to_zero(self):
        ecc = mock.Mock()
        ecc.get_privkey.return_value = os.urandom(32)
        msg = mock.Mock()
        msg.eth_account = '0x' + 40 * '0'

        res = helpers.process_report_computed_task(msg, ecc, mock.Mock())
        assert isinstance(res, message.tasks.RejectReportComputedTask)
