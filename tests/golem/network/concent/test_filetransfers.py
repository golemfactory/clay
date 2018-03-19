import unittest

from golem_messages.message.concents import FileTransferToken

from golem.network.concent import filetransfers
from tests.factories.concent import ConcentFileRequestFactory


class ConcentFileRequestTest(unittest.TestCase):
    def setUp(self):
        self.file_path = '/dev/null'

    def test_concent_file_request(self):
        def success():
            pass

        def error():
            pass

        cfr = ConcentFileRequestFactory(
            file_path=self.file_path, success=success, error=error)
        self.assertIsInstance(cfr, filetransfers.ConcentFileRequest)
        self.assertIsInstance(cfr.file_transfer_token, FileTransferToken)
        self.assertEqual(cfr.success, success)
        self.assertEqual(cfr.error, error)
