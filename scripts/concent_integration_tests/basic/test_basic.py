import logging
import unittest

from golem_messages import cryptography
from golem.network.concent import client
from golem.network.concent.exceptions import ConcentRequestError

from tests.factories import messages as msg_factories

from ..base import ConcentBaseTest


logger = logging.getLogger(__name__)


class SendTest(ConcentBaseTest, unittest.TestCase):
    def test_send(self):
        msg = msg_factories.ForceReportComputedTask()

        logger.debug("Sending FRCT: %s", msg)

        response = self._send_to_concent(msg)

        self.assertIsNone(
            response,
            msg="Expected nothing, got %s" % (
                self._load_response(response) if response else None
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
