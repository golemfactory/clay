import unittest

from golem_messages import factories as msg_factories
from golem_messages.message import concents as concent_msg
from golem_messages.message import tasks as tasks_msg

from ..base import ConcentDepositBaseTest


class SubtaskResultsVerifyTest(ConcentDepositBaseTest):

    def get_srv(self, **kwargs):
        rct_path = 'subtask_results_rejected__report_computed_task__'
        return msg_factories.concents.SubtaskResultsVerifyFactory(
            **self.gen_rtc_kwargs(rct_path),
            **self.gen_ttc_kwargs(rct_path + 'task_to_compute__'),
            subtask_results_rejected__sign__privkey=self.requestor_priv_key,
            **kwargs,
        )

    def get_correct_srv(self, **kwargs):
        vn = tasks_msg.SubtaskResultsRejected.REASON.VerificationNegative
        return self.get_srv(subtask_results_rejected__reason=vn, **kwargs)

    def test_send_srv_reason_incorrect(self):
        srv = self.get_srv()
        response = self.provider_send(srv)
        msg = self.provider_load_response(response)
        self.assertIsInstance(msg, concent_msg.ServiceRefused)
        self.assertEqual(
            msg.REASON,
            concent_msg.ServiceRefused.REASON.InvalidRequest
        )

    def test_send_srv_no_deposit(self):
        srv = self.get_correct_srv()
        response = self.provider_send(srv)
        msg = self.provider_load_response(response)
        self.assertIsInstance(msg, concent_msg.ServiceRefused)
        self.assertEqual(
            msg.REASON,
            concent_msg.ServiceRefused.REASON.TooSmallRequestorDeposit
        )

    def test_send(self):
        srv = self.get_correct_srv()
        response = self.provider_send(srv)
        msg = self.provider_load_response(response)
        self.assertIsInstance(msg, concent_msg.AckSubtaskResultsVerify)
        self.assertEqual(msg.subtask_results_verify, srv)
