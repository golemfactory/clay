from golem_messages import message

from .base import SubtaskResultsVerifyBaseTest


class SubtaskResultsVerifyTest(SubtaskResultsVerifyBaseTest):

    def test_send_srv_reason_incorrect(self):
        srv = self.get_srv(subtask_results_rejected__reason=None)
        response = self.provider_send(srv)
        msg = self.provider_load_response(response)
        self.assertIsInstance(msg, message.concents.ServiceRefused)
        self.assertEqual(
            msg.reason,
            message.concents.ServiceRefused.REASON.InvalidRequest
        )

    def test_send_srv_no_deposit(self):
        srv = self.get_correct_srv()
        response = self.provider_send(srv)
        msg = self.provider_load_response(response)
        self.assertIsInstance(msg, message.concents.ServiceRefused)
        self.assertEqual(
            msg.reason,
            message.concents.ServiceRefused.REASON.TooSmallRequestorDeposit
        )

    def test_send(self):
        srv = self.get_srv_with_deposit()
        response = self.provider_send(srv)
        msg = self.provider_load_response(response)
        self.assertIsInstance(msg, message.concents.AckSubtaskResultsVerify)
        self.assertMessageEqual(msg.subtask_results_verify, srv)
        ftt = msg.file_transfer_token
        self.assertIsInstance(ftt, message.concents.FileTransferToken)
        self.assertTrue(ftt.is_upload)
        self.assertTrue(
            ftt.get_file_info(
                message.concents.FileTransferToken.FileInfo.Category.results)
        )
        self.assertTrue(
            ftt.get_file_info(
                message.concents.FileTransferToken.FileInfo.Category.resources)
        )
