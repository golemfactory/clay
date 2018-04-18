import logging
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
        arct_rcv.verify_signature(self.requestor_pub_key)

    def test_reject_rct_timeout(self):
        frct = self.get_frct()
        self.provider_send(frct)
        frct_rcv = self.requestor_receive()

        rrct = message.tasks.RejectReportComputedTask(
            task_to_compute=frct_rcv.report_computed_task.task_to_compute,
            reason=message.tasks.RejectReportComputedTask.
            REASON.SubtaskTimeLimitExceeded
        )

        response = self.requestor_send(rrct)
        raise Exception(response)
        # @todo need to figure out what exactly happens here

    def test_reject_rct_cannot_compute_task(self):
        pass
        # @todo

    def test_reject_rct_task_failure(self):
        pass
        # @todo
