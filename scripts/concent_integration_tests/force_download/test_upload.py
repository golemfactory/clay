import binascii
import os
import faker
import tempfile
import unittest

from unittest import mock

from golem_messages.message import concents as concent_msg

from golem.core.simplehash import SimpleHash
from golem.network.concent import client
from golem.network.concent.filetransfers import (
    ConcentFiletransferService, ConcentFileRequest
)

from tests.factories import messages as msg_factories

from ..base import ConcentBaseTest


class ForceGetTaskResultUploadTest(ConcentBaseTest, unittest.TestCase):
    def setUp(self):
        super().setUp()
        file = tempfile.NamedTemporaryFile(delete=False)
        file.write(faker.Faker().binary(length=1 << 16))
        file.close()
        self.filename = file.name
        self.addCleanup(os.unlink, self.filename)

        keys = mock.Mock(public_key=self.pub_key)
        self.filetransfers = ConcentFiletransferService(keys_auth=keys)

    @property
    def size(self):
        return os.path.getsize(self.filename)

    @property
    def hash(self):
        return 'sha1:' + binascii.hexlify(
            SimpleHash.hash_file(self.filename)
        ).decode()

    def test_upload(self):
        provider_key = self.op_keys.raw_pubkey
        rct = msg_factories.ReportComputedTask(
            task_to_compute__provider_public_key=provider_key,
            size=self.size,
            package_hash=self.hash
        )
        fgtr = msg_factories.ForceGetTaskResult(report_computed_task=rct)
        self._send_to_concent(fgtr, other_party_public_key=provider_key)

        fgtru = self._load_response(
            client.receive_from_concent(provider_key),
            priv_key=self.op_keys.raw_privkey
        )
        self.assertIsInstance(fgtru, concent_msg.ForceGetTaskResultUpload)
        ftt = fgtru.file_transfer_token

        file_request = ConcentFileRequest(self.filename, ftt)
        response = self.filetransfers.upload(file_request)

        raise Exception(response.content)
