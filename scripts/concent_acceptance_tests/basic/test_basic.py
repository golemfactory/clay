import logging
import unittest

from golem_messages import factories as msg_factories
from golem.network.concent import client
from golem.network.concent.exceptions import ConcentRequestError

from ..base import ConcentBaseTest


logger = logging.getLogger(__name__)


class SendTest(ConcentBaseTest, unittest.TestCase):
    def test_send(self):
        msg = msg_factories.concents.ForceReportComputedTaskFactory(
            **self.gen_rtc_kwargs('report_computed_task__'),
            **self.gen_ttc_kwargs('report_computed_task__task_to_compute__'),
        )

        logger.debug("Sending FRCT: %s", msg)

        response = self.provider_send(msg)

        self.assertIsNone(
            response,
            msg="Expected nothing, got %s" % (
                self.provider_load_response(response) if response else None
            )
        )

    def test_fail_signature_invalid(self):
        msg = msg_factories.concents.ForceReportComputedTaskFactory()
        with self.assertRaisesRegex(
            ConcentRequestError,
            '.*exception when validating if golem_message'
            '.* is signed with public key'
        ):
            self.send_to_concent(msg)


class ReceiveTest(ConcentBaseTest, unittest.TestCase):
    def test_receive(self):
        content = client.receive_from_concent(
            signing_key=self.provider_priv_key,
            public_key=self.provider_pub_key,
            concent_variant=self.variant,
        )
        self.assertIsNone(content)
