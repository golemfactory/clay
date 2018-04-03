import base64
import unittest

from golem_messages import cryptography
from golem.network.concent import client
from golem.network.concent.exceptions import ConcentRequestError

from tests.factories import messages as msg_factories

from ..base import ConcentBaseTest


class SendTest(ConcentBaseTest, unittest.TestCase):
    def test_send(self):
        msg = msg_factories.ForceReportComputedTask()
        response = self._send_to_concent(msg)

        self.assertIsNone(
            response,
            msg="Expected nothing, got %s" % (
                base64.standard_b64decode(response) if response else None
            )
        )

    def test_fail_signature_invalid(self):
        msg = msg_factories.ForceReportComputedTask()
        keys = cryptography.ECCx(None)
        with self.assertRaises(ConcentRequestError) as context:
            self._send_to_concent(msg, keys.raw_privkey)

        self.assertIn('Failed to decode a Golem Message',
                      context.exception.args[0])


class ReceiveTest(ConcentBaseTest, unittest.TestCase):
    def test_receive(self):
        content = client.receive_from_concent(self.pub_key)
        self.assertIsNone(content)
