import calendar
import datetime
import unittest

from golem_messages import constants
from golem_messages import factories as msg_factories
from golem_messages import helpers
from golem_messages import message

from ..base import ConcentBaseTest


reasons = message.concents.ForceSubtaskResultsRejected.REASON
moment = datetime.timedelta(seconds=1)


class RequestorDoesntSendTestCase(ConcentBaseTest, unittest.TestCase):
    """Requestor doesn't send Acccept/Reject of SubtaskResults"""
    def provider_send_force(self, **kwargs):
        fsr = msg_factories.concents.ForceSubtaskResultsFactory(
            **self.gen_rtc_kwargs(
                'ack_report_computed_task__'
                'report_computed_task__'),
            **self.gen_ttc_kwargs(
                'ack_report_computed_task__'
                'report_computed_task__'
                'task_to_compute__'),
            **kwargs,
        )
        response = self.provider_load_response(self.provider_send(fsr))
        self.assertIn(
            type(response),
            [
                type(None),
                message.concents.ServiceRefused,
                message.concents.ForceSubtaskResultsRejected,
            ],
        )
        return response

    def test_provider_insufficient_funds(self):
        # TODO implement when we actually implement
        # the Concent communication fee
        # Concent should immidiately respond with MessageServiceRefused
        pass

    def test_provider_before_start(self):
        report_computed_task = msg_factories.tasks.ReportComputedTaskFactory()
        force_accept_window_begins_at = datetime.datetime.utcnow() \
            - helpers.subtask_verification_time(report_computed_task)
        msg_factories.helpers.override_timestamp(
            msg=report_computed_task.task_to_compute,
            timestamp=calendar.timegm(
                (force_accept_window_begins_at + moment).utctimetuple(),
            ),
        )
        response = self.provider_send_force(
            ack_report_computed_task__report_computed_task=report_computed_task,
        )
        self.assertIsInstance(
            response,
            message.concents.ForceSubtaskResultsRejected,
        )
        self.assertIs(
            response.reason,
            reasons.RequestPremature,
        )

    def test_provider_after_deadline(self):
        report_computed_task = msg_factories.tasks.ReportComputedTaskFactory()
        force_accept_window_ends_at = datetime.datetime.utcnow() - (
            helpers.subtask_verification_time(report_computed_task)
            + constants.FAT
        )
        msg_factories.helpers.override_timestamp(
            msg=report_computed_task.task_to_compute,
            timestamp=calendar.timegm(
                (force_accept_window_ends_at - moment).utctimetuple(),
            ),
        )

        response = self.provider_send_force(
            ack_report_computed_task__report_computed_task=report_computed_task,
        )
        self.assertIsInstance(
            response,
            message.concents.ForceSubtaskResultsRejected,
        )
        self.assertIs(
            response.reason,
            reasons.RequestTooLate,
        )

    def test_already_processed(self):
        response = self.provider_send_force()
        self.assertNotIsInstance(response, message.concents.ServiceRefused)
        second_response = self.provider_send_force()
        self.assertIsInstance(second_response, message.concents.ServiceRefused)

    def test_no_response_from_requestor(self):
        # No test, because of long sleep.
        pass

    def test_requestor_responds_with_invalid_accept(self):
        self.provider_send_force()
        fsrr = msg_factories.concents.ForceSubtaskResultsResponseFactory()
        fsrr.subtask_results_rejected = None
        response = self.requestor_send(fsrr)
        self.assertIsInstance(
            response,
            message.concents.ServiceRefused,
        )
        received = self.provider_receive()
        self.assertIsInstance(
            received,
            None,
        )

    def test_requestor_responds_with_invalid_reject(self):
        self.provider_send_force()
        fsrr = msg_factories.concents.ForceSubtaskResultsResponseFactory()
        fsrr.subtask_results_accepted = None
        response = self.requestor_send(fsrr)
        self.assertIsInstance(
            response,
            message.concents.ServiceRefused,
        )
        received = self.provider_receive()
        self.assertIsInstance(
            received,
            None,
        )

    def test_requestor_responds_with_accept(self):
        response = self.provider_send_force()
        self.assertIsNone(response)
        fsr = self.requestor_receive()
        # Check providers signature
        self.assertTrue(
            fsr.ack_report_computed_task.verify_signature(
                self.provider_pub_key,
            ),
        )
        accept_msg = msg_factories.tasks.SubtaskResultsAcceptedFactory(
            task_to_compute=fsr
            .ack_report_computed_task
            .report_computed_task
            .task_to_compute,
        )
        accept_msg.sign_message(self.requestor_priv_key)
        fsrr = message.concents.ForceSubtaskResultsResponse(
            subtask_results_accepted=accept_msg,
        )
        self.requestor_send(fsrr)
        received = self.provider_receive()
        self.assertIsInstance(
            received,
            message.concents.ForceSubtaskResultsResponse,
        )
        self.assertTrue(
            received.subtask_results_accepted.verify_signature(
                self.requestor_pub_key,
            ),
        )
        self.assertIsNone(received.subtask_results_rejected)
        self.assertEqual(received.subtask_results_accepted, accept_msg)

    def test_requestor_responds_with_reject(self):
        self.provider_send_force()
        fsr = self.requestor_receive()
        # Check providers signature
        self.assertTrue(
            fsr.ack_report_computed_task.verify_signature(
                self.provider_pub_key,
            ),
        )
        reject_msg = msg_factories.tasks.SubtaskResultsRejectedFactory(
            task_to_compute=fsr
            .ack_report_computed_task
            .report_computed_task
            .task_to_compute,
        )
        reject_msg.sign_message(self.requestor_priv_key)
        fsrr = message.concents.ForceSubtaskResultsResponse(
            subtask_results_rejected=reject_msg,
        )
        self.requestor_send(fsrr)
        received = self.provider_receive()
        self.assertIsInstance(
            received,
            message.concents.ForceSubtaskResultsResponse,
        )
        self.assertTrue(
            received.subtask_results_accepted.verify_signature(
                self.requestor_pub_key,
            ),
        )
        self.assertIsNone(received.subtask_results_accepted)
        self.assertEqual(received.subtask_results_rejected, reject_msg)
