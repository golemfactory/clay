from golem_messages.message import concents as concent_msg

from .base import SubtaskResultsVerifyBaseTest


class SubtaskResultsVerifyTest(SubtaskResultsVerifyBaseTest):

    def test_send_srv_reason_incorrect(self):
        srv = self.get_srv()
        response = self.provider_send(srv)
        msg = self.provider_load_response(response)
        self.assertIsInstance(msg, concent_msg.ServiceRefused)
        self.assertEqual(
            msg.reason,
            concent_msg.ServiceRefused.REASON.InvalidRequest
        )

    def test_send_srv_no_deposit(self):
        srv = self.get_correct_srv()
        response = self.provider_send(srv)
        msg = self.provider_load_response(response)
        self.assertIsInstance(msg, concent_msg.ServiceRefused)
        self.assertEqual(
            msg.reason,
            concent_msg.ServiceRefused.REASON.TooSmallRequestorDeposit
        )

    def test_send(self):
        srv = self.get_srv_with_deposit()
        response = self.provider_send(srv)
        msg = self.provider_load_response(response)
        self.assertIsInstance(msg, concent_msg.AckSubtaskResultsVerify)
        self.assertEqual(msg.subtask_results_verify, srv)
        ftt = msg.file_transfer_token
        self.assertIsInstance(ftt, concent_msg.FileTransferToken)
        self.assertTrue(ftt.is_upload)
        self.assertTrue(
            ftt.get_file_info(
                concent_msg.FileTransferToken.FileInfo.Category.results))
        self.assertTrue(
            ftt.get_file_info(
                concent_msg.FileTransferToken.FileInfo.Category.resources))
