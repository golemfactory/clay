import base64
import binascii
import filecmp
import logging
import os
import tempfile
import shutil
import unittest
from unittest import mock

import faker

from golem_messages import factories as msg_factories
from golem_messages.message import concents as concent_msg

from golem.core.simplehash import SimpleHash
from golem.network.concent import client
from golem.network.concent.filetransfers import (
    ConcentFiletransferService, ConcentFileRequest
)

from ..base import ConcentBaseTest


logger = logging.getLogger(__name__)


class ForceGetTaskResultFiletransferTest(ConcentBaseTest, unittest.TestCase):
    def setUp(self):
        super().setUp()
        file = tempfile.NamedTemporaryFile(delete=False)
        file.write(faker.Faker().binary(length=1 << 16))
        file.close()
        self.filename = file.name
        self.addCleanup(os.unlink, self.filename)

        self.provider_cfts = ConcentFiletransferService(
            keys_auth=mock.Mock(public_key=self.op_keys.raw_pubkey))
        self.requestor_cfts = ConcentFiletransferService(
            keys_auth=mock.Mock(public_key=self.keys.raw_pubkey))

    @property
    def size(self):
        return os.path.getsize(self.filename)

    @property
    def hash(self):
        return 'sha1:' + binascii.hexlify(
            SimpleHash.hash_file(self.filename)
        ).decode()

    def get_fgtru(self):
        provider_keys = self.op_keys

        logger.debug('Provider key: %s',
                     base64.b64encode(provider_keys.raw_pubkey).decode())

        rct = msg_factories.tasks.ReportComputedTaskFactory(
            task_to_compute__provider_public_key=self.op_keys.raw_pubkey,
            size=self.size,
            package_hash=self.hash
        )
        fgtr = msg_factories.concents.ForceGetTaskResultFactory(
            report_computed_task=rct)
        self.send_to_concent(
            fgtr, other_party_public_key=provider_keys.raw_pubkey)

        response = client.receive_from_concent(
            signing_key=provider_keys.raw_privkey,
            public_key=provider_keys.raw_pubkey
        )
        return self.load_response(
            response, priv_key=provider_keys.raw_privkey)

    @staticmethod
    def _log_concent_response(response):
        logger.debug(
            "Concent response - status: %s, head: '%s', body: '%s'",
            response.status_code, response.headers, response.content
        )

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

        fgtrd = self.load_response(
            client.receive_from_concent(self.priv_key, self.pub_key)
        )
        self.assertIsInstance(fgtrd, concent_msg.ForceGetTaskResultDownload)
        self.assertEqual(fgtrd.subtask_id, fgtru.subtask_id)
        self.assertSamePayload(
            fgtru.force_get_task_result, fgtrd.force_get_task_result)

        ftt = fgtrd.file_transfer_token
        self.assertFttCorrect(
            ftt,
            subtask_id=fgtru.subtask_id,
            client_key=self.pub_key,
            operation=ftt.Operation.download
        )

        download_dir = tempfile.mkdtemp()
        download_filename = download_dir + '/download.zip'

        file_request = ConcentFileRequest(download_filename, ftt)
        response = self.requestor_cfts.download(file_request)
        self.assertEqual(response.status_code, 200)

        self.assertTrue(filecmp.cmp(self.filename, download_filename))

        shutil.rmtree(download_dir)
