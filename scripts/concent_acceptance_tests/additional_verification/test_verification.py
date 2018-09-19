import time

from unittest import mock

from golem_messages.message import concents as concent_msg
from golem_messages.message import tasks as tasks_msg


from golem.network.concent.filetransfers import (
    ConcentFiletransferService, ConcentFileRequest
)

from .base import SubtaskResultsVerifyBaseTest


class SubtaskResultsVerifyFiletransferTest(SubtaskResultsVerifyBaseTest):
    TIMEOUT = 300
    INTERVAL = 10

    def setUp(self):
        super(SubtaskResultsVerifyFiletransferTest, self).setUp()
        self.provider_cfts = ConcentFiletransferService(
            keys_auth=mock.Mock(
                public_key=self.provider_pub_key,
                _private_key=self.provider_priv_key
            ),
            variant=self.variant,
        )

    def perform_upload(self, request):
        response = self.provider_cfts.upload(request)
        self._log_concent_response(response)
        self.assertEqual(response.status_code, 200)

    def upload_files(self, ftt, resources_filename, results_filename):
        self.perform_upload(
            ConcentFileRequest(
                str(resources_filename),
                ftt,
                file_category=concent_msg.FileTransferToken.FileInfo.
                Category.resources
            )
        )

        self.perform_upload(
            ConcentFileRequest(
                str(results_filename),
                ftt,
                file_category=concent_msg.FileTransferToken.FileInfo.
                Category.results
            )
        )

    def test_verify(self):
        srv = self.get_srv_with_deposit(self.results_filename)
        response = self.provider_send(srv)
        asrv = self.provider_load_response(response)
        self.assertIsInstance(asrv, concent_msg.AckSubtaskResultsVerify)

        ftt = asrv.file_transfer_token

        self.upload_files(ftt, self.resources_filename,
                          self.results_filename)

        verification_start = time.time()

        while time.time() < verification_start + self.TIMEOUT:
            response = self.provider_receive()
            if response:
                self.assertIsInstance(response,
                                      concent_msg.SubtaskResultsSettled)
                self.assertSamePayload(
                    response.task_to_compute,
                    srv.subtask_results_rejected.
                    report_computed_task.task_to_compute
                )
                return
            time.sleep(self.INTERVAL)

        raise AssertionError("Verification timed out")

    def test_verify_negative(self):
        srv = self.get_srv_with_deposit(self.results_corrupt_filename)
        response = self.provider_send(srv)
        asrv = self.provider_load_response(response)
        self.assertIsInstance(asrv, concent_msg.AckSubtaskResultsVerify)

        ftt = asrv.file_transfer_token

        self.upload_files(ftt, self.resources_filename,
                          self.results_corrupt_filename)
        verification_start = time.time()

        while time.time() < verification_start + self.TIMEOUT:
            response = self.provider_receive()
            if response:
                self.assertIsInstance(response,
                                      tasks_msg.SubtaskResultsRejected)
                self.assertSamePayload(
                    response.report_computed_task,
                    srv.subtask_results_rejected.report_computed_task
                )
                return
            time.sleep(self.INTERVAL)

        raise AssertionError("Verification timed out")
