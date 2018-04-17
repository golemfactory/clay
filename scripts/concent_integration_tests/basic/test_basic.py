import logging
import unittest

from golem_messages import cryptography
from golem_messages import factories as msg_factories
from golem.network.concent import client
from golem.network.concent.exceptions import ConcentRequestError

from ..base import ConcentBaseTest


logger = logging.getLogger(__name__)


class SendTest(ConcentBaseTest, unittest.TestCase):
    def test_send(self):
        msg = msg_factories.concents.ForceReportComputedTaskFactory()

        logger.debug("Sending FRCT: %s", msg)

        response = self.send_to_concent(msg)

        self.assertIsNone(
            response,
            msg="Expected nothing, got %s" % (
                self.load_response(response) if response else None
            )
        )

    def test_fail_signature_invalid(self):
        msg = msg_factories.concents.ForceReportComputedTaskFactory()
        keys = cryptography.ECCx(None)
        with self.assertRaises(ConcentRequestError) as context:
            self.send_to_concent(msg, keys.raw_privkey)

        self.assertIn('Failed to decode a Golem Message',
                      context.exception.args[0])


class ReceiveTest(ConcentBaseTest, unittest.TestCase):
    def test_receive(self):
        content = client.receive_from_concent(
            signing_key=self.priv_key, public_key=self.pub_key)
        self.assertIsNone(content)
