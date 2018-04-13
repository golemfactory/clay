import calendar
import datetime
import logging
import time

import unittest

from golem_messages.message import concents as concent_msg

from golem.network.concent import client

from tests.factories import messages as msg_factories

from ..base import ConcentBaseTest


logger = logging.getLogger(__name__)


class ForceGetTaskResultTest(ConcentBaseTest, unittest.TestCase):

    def test_send(self):
        fgtr = msg_factories.ForceGetTaskResult()
        response = self._send_to_concent(fgtr)
        msg = self._load_response(response)
        self.assertIsInstance(msg, concent_msg.AckForceGetTaskResult)
        self.assertSameMessage(msg.force_get_task_result, fgtr)

    def test_send_fail_timeout(self):
        past_deadline = calendar.timegm(time.gmtime()) -\
                        int(datetime.timedelta(days=1).total_seconds())
        ttc = msg_factories.TaskToCompute(
            compute_task_def__deadline=past_deadline
        )
        fgtr = msg_factories.ForceGetTaskResult(
            report_computed_task__task_to_compute=ttc
        )

        response = self._send_to_concent(fgtr)
        msg = self._load_response(response)
        self.assertIsInstance(msg, concent_msg.ForceGetTaskResultRejected)
        self.assertEqual(msg.reason,
                         msg.REASON.AcceptanceTimeLimitExceeded)

    def test_send_duplicate(self):
        rct = msg_factories.ReportComputedTask()
        fgtr1 = msg_factories.ForceGetTaskResult(report_computed_task=rct)

        response = self._send_to_concent(fgtr1)
        msg = self._load_response(response)
        self.assertIsInstance(msg, concent_msg.AckForceGetTaskResult)

        fgtr2 = msg_factories.ForceGetTaskResult(report_computed_task=rct)

        response = self._send_to_concent(fgtr2)
        msg = self._load_response(response)
        self.assertIsInstance(msg, concent_msg.ServiceRefused)
        self.assertEqual(msg.reason, msg.REASON.DuplicateRequest)

    def test_provider_receive(self):
        provider_key = self.op_keys.raw_pubkey
        fgtr = msg_factories.ForceGetTaskResult()

        fgtr.report_computed_task.task_to_compute.provider_public_key = \
            provider_key

        logger.debug("requestor sent ForceGetTaskResult: %s", fgtr)

        ack = self._load_response(
            self._send_to_concent(fgtr, other_party_public_key=provider_key)
        )
        self.assertIsInstance(ack, concent_msg.AckForceGetTaskResult)
        fgtru = self._load_response(
            client.receive_from_concent(provider_key),
            priv_key=self.op_keys.raw_privkey
        )
        self.assertIsInstance(fgtru, concent_msg.ForceGetTaskResultUpload)
        self.assertSamePayload(fgtru.force_get_task_result, fgtr)

        logger.debug("provider received ForceGetTaskResultUpload: %s", fgtru)

        ftt = fgtru.file_transfer_token
        self.assertFttCorrect(
            ftt,
            subtask_id=fgtr.subtask_id,
            client_key=provider_key,
            operation=ftt.Operation.upload
        )
