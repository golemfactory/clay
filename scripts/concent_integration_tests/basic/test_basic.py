import unittest

from golem_messages import cryptography
from golem.network.concent import client
from golem.network.concent.exceptions import ConcentRequestError

from tests.factories import messages as msg_factories

from ..base import ConcentBaseTest


class SendTest(ConcentBaseTest, unittest.TestCase):
    def test_send(self):
        msg = msg_factories.ForceReportComputedTask()
        content = client.send_to_concent(msg, self.priv_key, self.pub_key)
        self.assertIsNone(content)

    def test_fail_signature_invalid(self):
        msg = msg_factories.ForceReportComputedTask()
        keys = cryptography.ECCx(None)
        with self.assertRaises(ConcentRequestError) as context:
            client.send_to_concent(msg, keys.raw_privkey, self.pub_key)

        self.assertIn('Failed to decode a Golem Message',
                      context.exception.args[0])


class ReceiveTest(ConcentBaseTest, unittest.TestCase):
    def test_receive(self):
        content = client.receive_from_concent(self.pub_key)
        self.assertIsNone(content)
