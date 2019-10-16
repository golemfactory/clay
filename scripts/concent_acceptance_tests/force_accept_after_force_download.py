import datetime
import logging
import time

from golem_messages import message

from golem.network.concent.filetransfers import ConcentFileRequest

from .force_download.test_filetransfers import TestBase as ForceDownloadTestBase
from .force_accept.test_requestor_doesnt_send import TestBase \
    as ForceAcceptTestBase

logger = logging.getLogger(__name__)


class Test(ForceDownloadTestBase, ForceAcceptTestBase):
    def _test_upload_fail(self):
        wrong_hash = "sha1:adeab1829629b4e1a19dc197f2e85603ee0b5cb4"
        offset_seconds = 61
        fgtr = self.get_fgtr(
            ttc_kwargs={
                'compute_task_def__deadline': int(time.time()) + offset_seconds
            },
            report_computed_task__size=self.size,
            report_computed_task__package_hash=wrong_hash,
        )
        self.requestor_send(fgtr)
        fgtru = self.provider_receive()
        self.assertIsInstance(fgtru, message.concents.ForceGetTaskResultUpload)

        ftt = fgtru.file_transfer_token
        file_request = ConcentFileRequest(self.filename, ftt)
        upload_response = self.provider_cfts.upload(file_request)
        self._log_concent_response(upload_response)

        self.assertEqual(upload_response.status_code, 400)
        timeout = ftt.token_expiration_deadline + offset_seconds
        logger.debug("timeout: %s", datetime.datetime.fromtimestamp(timeout))
        fgtrf = None

        # Currently concent treats wrong hash as an upload that didn't took
        # place, so we have to wait for timeout.
        while not fgtrf and time.time() < timeout:
            fgtrf = self.requestor_receive()
            time.sleep(60)

        self.assertIsInstance(fgtrf, message.concents.ForceGetTaskResultFailed)
        self.assertEqual(fgtrf.subtask_id, fgtru.subtask_id)
        return fgtrf

    def test_requestor_responds_with_fgtrf(self):
        fgtrf = self._test_upload_fail()

        response_to_force = self.provider_send_force(ttc=fgtrf.task_to_compute)
        self.assertIsInstance(response_to_force,
                              message.concents.ServiceRefused)
        self.assertEqual(
            response_to_force.reason,
            message.concents.ServiceRefused.REASON.DuplicateRequest
        )
