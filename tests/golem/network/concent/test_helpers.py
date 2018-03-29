import unittest

from golem_messages import shortcuts as msg_shortcuts

from golem import testutils
from golem.core.keysauth import KeysAuth

from golem.network.concent.helpers import verify_message_signature

from tests.factories.messages import (
    ReportComputedTask as ReportComputedTaskFactory
)


class VerifyMessageSignatureTest(testutils.TempDirFixture,
                                 unittest.TestCase):
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
        sig_ok = verify_message_signature(
            msg_shortcuts.load(msg_dump, None, self.keys_auth.public_key),
            self.keys_auth.ecc)

        self.assertTrue(sig_ok)

    def test_verify_fail(self):
        msg = ReportComputedTaskFactory()
        msg_dump = msg_shortcuts.dump(msg,
                                      self.other_keys._private_key,
                                      None)
        sig_ok = verify_message_signature(
            msg_shortcuts.load(msg_dump, None, self.other_keys.public_key),
            self.keys_auth.ecc,
        )
        self.assertFalse(sig_ok)
