import calendar
import datetime
import logging
import time
import unittest

from golem_messages import factories as msg_factories
from golem_messages import message

from ..base import ConcentBaseTest


logger = logging.getLogger(__name__)


class ForceReportComputedTaskTest(ConcentBaseTest, unittest.TestCase):

    def get_frct(self, **kwargs):
        return msg_factories.concents.ForceReportComputedTaskFactory(
            **self.gen_rtc_kwargs('report_computed_task__'),
            **self.gen_ttc_kwargs('report_computed_task__task_to_compute__'),
            **kwargs,
        )

    def test_send(self):
        frct = self.get_frct()
        response = self.provider_send(frct)
        self.assertIsNone(response)

    def test_send_ttc_deadline_float(self):
        deadline = calendar.timegm(time.gmtime()) + \
                   datetime.timedelta(days=1, microseconds=123).total_seconds()
        frct = self.get_frct(report_computed_task__task_to_compute__compute_task_def__deadline=deadline)  # noqa pylint:disable=line-too-long
        response = self.provider_send(frct)
        self.assertIsNone(response)

    def test_provider_insufficient_funds(self):
        # @todo implement when we actually implement
        # the Concent communication fee
        pass

    def test_task_timeout(self):
        ttc = msg_factories.tasks.TaskToComputeFactory.past_deadline(
            **self.gen_ttc_kwargs(),
        )
        frct = msg_factories.concents.ForceReportComputedTaskFactory(
            report_computed_task__task_to_compute=ttc,
            **self.gen_rtc_kwargs('report_computed_task__'),
        )
        response = self.provider_send(frct)
        msg = self.provider_load_response(response)
        self.assertIsInstance(
            msg,
            message.concents.ForceReportComputedTaskResponse)
        self.assertEqual(
            msg.reason,
            message.concents.ForceReportComputedTaskResponse.
            REASON.SubtaskTimeout
        )

    def test_requestor_receive(self):
        frct = self.get_frct()
        self.provider_send(frct)
        frct_rcv = self.requestor_receive()
        self.assertEqual(frct.report_computed_task,
                         frct_rcv.report_computed_task)

    ###
    #
    # we have no way to _sensibly_ test the "Concent fails to contact the
    # Requestor" scenario as it would require us to either enforce an explicit
    # state within the Concent Service - or - wait until the timeout happens
    # (currently set at one hour)
    #
    ###

    def test_ack_rct(self):
        frct = self.get_frct()
        self.provider_send(frct)
        frct_rcv = self.requestor_receive()

        arct = message.tasks.AckReportComputedTask(
            report_computed_task=frct_rcv.report_computed_task
        )

        response = self.requestor_send(arct)
        self.assertIsNone(response)

        frct_response = self.provider_receive()
        self.assertIsInstance(
            frct_response, message.concents.ForceReportComputedTaskResponse)

        arct_rcv = frct_response.ack_report_computed_task
        self.assertIsInstance(
            arct_rcv, message.tasks.AckReportComputedTask)
        self.assertEqual(
            frct_response.reason,
            message.concents.ForceReportComputedTaskResponse.
            REASON.AckFromRequestor
        )
        arct_rcv.verify_signature(self.requestor_pub_key)

    def test_reject_rct_timeout(self):
        frct = self.get_frct()
        self.provider_send(frct)
        frct_rcv = self.requestor_receive()

        rrct = message.tasks.RejectReportComputedTask(
            attached_task_to_compute=frct_rcv.
            report_computed_task.task_to_compute,
            reason=message.tasks.RejectReportComputedTask.
            REASON.SubtaskTimeLimitExceeded
        )

        response = self.requestor_send(rrct)

        # @todo ensure that `None` is the correct response here
        # I have a feeling it should be `VerdictReportComputedTask`

        self.assertIsNone(response)

        frct_response = self.provider_receive()
        self.assertIsInstance(
            frct_response, message.concents.ForceReportComputedTaskResponse)

        arct_rcv = frct_response.ack_report_computed_task
        self.assertIsInstance(arct_rcv, message.tasks.AckReportComputedTask)
        arct_rcv.verify_signature(self.variant['pubkey'])
        self.assertEqual(arct_rcv.report_computed_task,
                         frct.report_computed_task)

    def send_and_verify_received_reject(self, rrct):
        response = self.requestor_send(rrct)
        self.assertIsNone(response)

        frct_response = self.provider_receive()
        self.assertIsInstance(
            frct_response, message.concents.ForceReportComputedTaskResponse)
        self.assertEqual(
            frct_response.reason,
            message.concents.ForceReportComputedTaskResponse.
            REASON.RejectFromRequestor
        )
        rrct_rcv = frct_response.reject_report_computed_task
        rrct_rcv.verify_signature(self.requestor_pub_key)
        self.assertEqual(rrct_rcv, rrct)

    def test_reject_rct_cannot_compute_task(self):
        frct = self.get_frct()
        self.provider_send(frct)
        self.requestor_receive()

        ttc = frct.report_computed_task.task_to_compute  # noqa pylint:disable=no-member
        cct = msg_factories.tasks.CannotComputeTaskFactory(
            task_to_compute=ttc,
            sign__privkey=self.provider_priv_key,
            reason=message.tasks.CannotComputeTask.REASON.NoSourceCode,
        )

        rrct = message.tasks.RejectReportComputedTask(
            cannot_compute_task=cct,
            reason=message.tasks.RejectReportComputedTask.
            REASON.GotMessageCannotComputeTask,
        )

        self.assertEqual(rrct.task_to_compute, ttc)
        self.send_and_verify_received_reject(rrct)

    def test_reject_rct_task_failure(self):
        frct = self.get_frct()
        self.provider_send(frct)
        self.requestor_receive()

        ttc = frct.report_computed_task.task_to_compute  # noqa pylint:disable=no-member
        tf = msg_factories.tasks.TaskFailureFactory(
            task_to_compute=ttc,
            sign__privkey=self.provider_priv_key,
        )

        rrct = message.tasks.RejectReportComputedTask(
            task_failure=tf,
            reason=message.tasks.RejectReportComputedTask.
            REASON.GotMessageTaskFailure,
        )

        self.assertEqual(rrct.task_to_compute, ttc)
        self.send_and_verify_received_reject(rrct)
