import binascii
import datetime
import filecmp
import logging
import os
import tempfile
import time
import shutil
import unittest
from unittest import mock

import faker

from golem_messages.message import concents as concent_msg

from golem.core.simplehash import SimpleHash
from golem.network.concent.filetransfers import (
    ConcentFiletransferService, ConcentFileRequest
)

from .base import ForceDownloadBaseTest


logger = logging.getLogger(__name__)


class ForceGetTaskResultFiletransferTest(ForceDownloadBaseTest,
                                         unittest.TestCase):

    def setUp(self):
        super().setUp()
        file = tempfile.NamedTemporaryFile(delete=False)
        file.write(faker.Faker().binary(length=1 << 16))
        file.close()
        self.filename = file.name
        self.addCleanup(os.unlink, self.filename)

        self.provider_cfts = ConcentFiletransferService(
            keys_auth=mock.Mock(
                public_key=self.provider_pub_key,
                _private_key=self.provider_priv_key
            ),
            variant=self.variant,
        )
        self.requestor_cfts = ConcentFiletransferService(
            keys_auth=mock.Mock(
                public_key=self.requestor_pub_key,
                _private_key=self.requestor_priv_key
            ),
            variant=self.variant,
        )

    @property
    def size(self):
        return os.path.getsize(self.filename)

    @property
    def hash(self):
        return 'sha1:' + binascii.hexlify(
            SimpleHash.hash_file(self.filename)
        ).decode()

    def get_fgtru(self):
        fgtr = self.get_fgtr(
            report_computed_task__size=self.size,
            report_computed_task__package_hash=self.hash
        )
        self.requestor_send(fgtr)
        return self.provider_receive()

    def test_upload(self):
        fgtru = self.get_fgtru()
        self.assertIsInstance(fgtru, concent_msg.ForceGetTaskResultUpload)

        ftt = fgtru.file_transfer_token
        file_request = ConcentFileRequest(self.filename, ftt)
        response = self.provider_cfts.upload(file_request)
        self._log_concent_response(response)

        self.assertEqual(response.status_code, 200)
        # @todo some additional checks ?

    def test_download(self):
        fgtru = self.get_fgtru()
        self.assertIsInstance(fgtru, concent_msg.ForceGetTaskResultUpload)

        upload_response = self.provider_cfts.upload(
            ConcentFileRequest(self.filename, fgtru.file_transfer_token))
        self._log_concent_response(upload_response)

        self.assertEqual(upload_response.status_code, 200)
        timeout = datetime.datetime.now() + datetime.timedelta(seconds=10)
        fgtrd = None

        # we may need to retry because the message goes through a queue
        # inside Concent's storage cluster
        while not fgtrd and datetime.datetime.now() < timeout:
            fgtrd = self.requestor_receive()
            time.sleep(1)

        self.assertIsInstance(fgtrd, concent_msg.ForceGetTaskResultDownload)
        self.assertEqual(fgtrd.subtask_id, fgtru.subtask_id)
        self.assertSamePayload(
            fgtru.force_get_task_result, fgtrd.force_get_task_result)

        ftt = fgtrd.file_transfer_token
        self.assertFttCorrect(
            ftt,
            subtask_id=fgtru.subtask_id,
            client_key=self.requestor_pub_key,
            operation=ftt.Operation.download
        )

        download_dir = tempfile.mkdtemp()
        download_filename = download_dir + '/download.zip'

        file_request = ConcentFileRequest(download_filename, ftt)
        response = self.requestor_cfts.download(file_request)
        self.assertEqual(response.status_code, 200)

        self.assertTrue(filecmp.cmp(self.filename, download_filename))

        shutil.rmtree(download_dir)
