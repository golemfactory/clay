import logging
import unittest

from golem_messages import factories as msg_factories
from golem_messages import message

from ..base import ConcentBaseTest


logger = logging.getLogger(__name__)


class ForceReportComputedTaskTest(ConcentBaseTest, unittest.TestCase):

    def provider_send(self, msg):
        logger.debug("Provider sends %s" % msg)
        return self.send_to_concent(
            msg, other_party_public_key=self.op_keys.raw_pubkey
        )

    def requestor_send(self, msg):
        logger.debug("Requestor sends %s" % msg)
        return self.send_to_concent(
            msg,
            signing_key=self.op_keys.raw_privkey,
            public_key=self.op_keys.raw_pubkey,
            other_party_public_key=self.keys.raw_pubkey,
        )

    def provider_receive(self):
        response = self.receive_from_concent()
        if not response:
            logger.debug("Provider got empty response")
            return None

        msg = self.load_response(response)
        logger.debug("Provider receives %s" % msg)
        return msg

    def requestor_receive(self):
        response = self.receive_from_concent(
            signing_key=self.op_keys.raw_privkey,
            public_key=self.op_keys.raw_pubkey
        )
        if not response:
            logger.debug("Requestor got empty response")
            return None

        msg = self.load_response(
            response, priv_key=self.op_keys.raw_privkey
        )
        logger.debug("Requestor receives %s" % msg)
        return msg

    def test_send(self):
        frct = msg_factories.concents.ForceReportComputedTaskFactory()
        response = self.send_to_concent(frct)
        self.assertIsNone(response)

    def test_provider_insufficient_funds(self):
        # @todo implement when we actually implement
        # the Concent communication fee
        pass

    def test_task_timeout(self):
        ttc = msg_factories.tasks.TaskToComputeFactory.past_deadline()
        frct = msg_factories.concents.ForceGetTaskResultFactory(
            report_computed_task__task_to_compute=ttc
        )
        response = self.send_to_concent(frct)
        msg = self.load_response(response)
        self.assertIsInstance(msg, message.concents.ForceGetTaskResultRejected)
        self.assertEqual(
            msg.reason,
            message.concents.ForceGetTaskResultRejected.
                REASON.AcceptanceTimeLimitExceeded
        )

    def test_requestor_receive(self):
        frct = msg_factories.concents.ForceReportComputedTaskFactory()
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
        frct = msg_factories.concents.ForceReportComputedTaskFactory()
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
        arct_rcv.verify_signature(self.keys.raw_pubkey)

    def test_reject_rct_timeout(self):
        frct = msg_factories.concents.ForceReportComputedTaskFactory()
        self.provider_send(frct)
        frct_rcv = self.requestor_receive()

        rrct = message.tasks.RejectReportComputedTask(
            task_to_compute=frct_rcv.report_computed_task.task_to_compute,
            reason=message.tasks.RejectReportComputedTask.
                REASON.SubtaskTimeLimitExceeded
        )

        response = self.requestor_send(rrct)
        raise Exception(response)  # @todo need to figure out what exactly happens here

    def test_reject_rct_cannot_compute_task(self):
        raise Exception()
    