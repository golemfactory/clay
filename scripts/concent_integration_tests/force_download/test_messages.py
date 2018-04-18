import logging

import unittest

from golem_messages import factories as msg_factories
from golem_messages.message import concents as concent_msg

from golem.network.concent import client

from ..base import ConcentBaseTest


logger = logging.getLogger(__name__)


class ForceGetTaskResultTest(ConcentBaseTest, unittest.TestCase):

    def test_send(self):
        fgtr = msg_factories.concents.ForceGetTaskResultFactory()
        response = self.send_to_concent(fgtr)
        msg = self.load_response(response)
        self.assertIsInstance(msg, concent_msg.AckForceGetTaskResult)
        self.assertEqual(msg.force_get_task_result, fgtr)

    def test_send_fail_timeout(self):
        ttc = msg_factories.tasks.TaskToComputeFactory.past_deadline()
        fgtr = msg_factories.concents.ForceGetTaskResultFactory(
            report_computed_task__task_to_compute=ttc
        )

        response = self.send_to_concent(fgtr)
        msg = self.load_response(response)
        self.assertIsInstance(msg, concent_msg.ForceGetTaskResultRejected)
        self.assertEqual(msg.reason,
                         msg.REASON.AcceptanceTimeLimitExceeded)

    def test_send_duplicate(self):
        rct = msg_factories.tasks.ReportComputedTaskFactory()
        fgtr1 = msg_factories.concents.ForceGetTaskResultFactory(
            report_computed_task=rct)

        response = self.send_to_concent(fgtr1)
        msg = self.load_response(response)
        self.assertIsInstance(msg, concent_msg.AckForceGetTaskResult)

        fgtr2 = msg_factories.concents.ForceGetTaskResultFactory(
            report_computed_task=rct)

        response = self.send_to_concent(fgtr2)
        msg = self.load_response(response)
        self.assertIsInstance(msg, concent_msg.ServiceRefused)
        self.assertEqual(msg.reason, msg.REASON.DuplicateRequest)

    def test_provider_receive(self):
        provider_key = self.op_keys.raw_pubkey
        fgtr = msg_factories.concents.ForceGetTaskResultFactory()

        fgtr.report_computed_task.task_to_compute.provider_public_key = \
            provider_key

        logger.debug("requestor sent ForceGetTaskResult: %s", fgtr)

        ack = self.load_response(
            self.send_to_concent(fgtr, other_party_public_key=provider_key)
        )
        self.assertIsInstance(ack, concent_msg.AckForceGetTaskResult)
        fgtru = self.load_response(
            client.receive_from_concent(
                self.op_keys.raw_privkey, provider_key),
            priv_key=self.op_keys.raw_privkey
        )
        self.assertIsInstance(fgtru, concent_msg.ForceGetTaskResultUpload)
        self.assertSamePayload(fgtru.force_get_task_result, fgtr)

        logger.debug("provider received ForceGetTaskResultUpload: %s", fgtru)

        ftt = fgtru.file_transfer_token
        logger.debug("Received FTT %s", ftt)
        self.assertFttCorrect(
            ftt,
            subtask_id=fgtr.subtask_id,
            client_key=provider_key,
            operation=ftt.Operation.upload
        )
