import logging

import unittest

from golem_messages import factories as msg_factories
from golem_messages.message import concents as concent_msg

from .base import ForceDownloadBaseTest


logger = logging.getLogger(__name__)


class ForceGetTaskResultTest(ForceDownloadBaseTest, unittest.TestCase):

    def test_send(self):
        fgtr = self.get_fgtr()
        response = self.requestor_send(fgtr)
        msg = self.requestor_load_response(response)
        self.assertIsInstance(msg, concent_msg.AckForceGetTaskResult)
        self.assertEqual(msg.force_get_task_result, fgtr)

    def test_send_fail_timeout(self):
        ttc = msg_factories.tasks.TaskToComputeFactory.past_deadline(
            **self.gen_ttc_kwargs(),
        )
        fgtr = msg_factories.concents.ForceGetTaskResultFactory(
            report_computed_task__task_to_compute=ttc,
            **self.gen_rtc_kwargs('report_computed_task__'),
        )
        response = self.requestor_send(fgtr)
        msg = self.requestor_load_response(response)
        self.assertIsInstance(msg, concent_msg.ForceGetTaskResultRejected)
        self.assertEqual(msg.reason,
                         msg.REASON.AcceptanceTimeLimitExceeded)

    def test_send_duplicate(self):
        fgtr1 = self.get_fgtr()
        response = self.requestor_send(fgtr1)
        msg = self.requestor_load_response(response)
        self.assertIsInstance(msg, concent_msg.AckForceGetTaskResult)

        fgtr2 = msg_factories.concents.ForceGetTaskResultFactory(
            report_computed_task=fgtr1.report_computed_task)

        response = self.requestor_send(fgtr2)
        msg = self.requestor_load_response(response)
        self.assertIsInstance(msg, concent_msg.ServiceRefused)
        self.assertEqual(msg.reason, msg.REASON.DuplicateRequest)

    def test_provider_receive(self):
        fgtr = self.get_fgtr()
        logger.debug("requestor sent ForceGetTaskResult: %s", fgtr)

        ack = self.requestor_load_response(
            self.requestor_send(fgtr)
        )
        self.assertIsInstance(ack, concent_msg.AckForceGetTaskResult)
        fgtru = self.provider_receive()
        self.assertIsInstance(fgtru, concent_msg.ForceGetTaskResultUpload)
        self.assertSamePayload(fgtru.force_get_task_result, fgtr)

        logger.debug("provider received ForceGetTaskResultUpload: %s", fgtru)

        ftt = fgtru.file_transfer_token
        logger.debug("Received FTT %s", ftt)
        self.assertFttCorrect(
            ftt,
            subtask_id=fgtr.subtask_id,
            client_key=self.provider_pub_key,
            operation=ftt.Operation.upload
        )
