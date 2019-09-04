import base64
import queue
import unittest

import mock

from golem_messages.factories.concents import (
    FileTransferTokenFactory, FileInfoFactory)
from golem_messages.message.concents import FileTransferToken

from golem import testutils
from golem import constants as gconst
from golem.core import keysauth
from golem.core import variables
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

        category = FileTransferToken.FileInfo.Category.resources

        cfr = ConcentFileRequestFactory(
            file_path=self.file_path,
            success=success, error=error,
            file_category=category)

        self.assertIsInstance(cfr, filetransfers.ConcentFileRequest)
        self.assertIsInstance(cfr.file_transfer_token, FileTransferToken)
        self.assertEqual(cfr.success, success)
        self.assertEqual(cfr.error, error)
        self.assertEqual(cfr.file_category, category)


class ConcentFiletransferServiceTest(testutils.TempDirFixture):

    def setUp(self):
        super().setUp()
        self.keys_auth = keysauth.KeysAuth(
            datadir=self.path,
            private_key_name='priv_key',
            password='password',
        )
        self.cfs = filetransfers.ConcentFiletransferService(
            keys_auth=self.keys_auth,
            variant=variables.CONCENT_CHOICES['dev'],
        )

    def _mock_get_auth_headers(self, file_transfer_token: FileTransferToken):
        return {
            'Authorization': 'Golem ' + base64.b64encode(
                file_transfer_token.serialize()).decode(),
            'X-Golem-Messages': str(gconst.GOLEM_MESSAGES_VERSION),
        }

    def tearDown(self):
        self.assertFalse(self.cfs.running)

    def test_init(self):
        self.assertIsInstance(self.cfs._transfers, queue.Queue)
        self.assertEqual(self.cfs.keys_auth, self.keys_auth)

    @mock.patch('golem.network.concent.filetransfers.LoopingCallService.start')
    def test_start(self, lcs_mock):
        self.cfs.start()
        lcs_mock.assert_called_once_with(now=True)

    @mock.patch('golem.network.concent.filetransfers.LoopingCallService.stop')
    def test_stop(self, lcs_mock):
        self.cfs.stop()
        lcs_mock.assert_called_once()

    @mock.patch('golem.network.concent.filetransfers.logger.warning')
    def test_transfer_unstarted(self, log_mock):
        self.cfs.transfer('/crucial/file.dat', FileTransferTokenFactory())
        log_mock.assert_called_once()
        self.assertIn('not started', log_mock.call_args[0][0])

    def test_transfer(self):
        category = FileTransferToken.FileInfo.Category.resources
        ftt = FileTransferTokenFactory()
        self.cfs.transfer('/less/important.txt', ftt, file_category=category)
        request = self.cfs._transfers.get()
        self.assertIsInstance(request, filetransfers.ConcentFileRequest)
        self.assertEqual(request.file_transfer_token, ftt)
        self.assertEqual(request.file_category, category)

    def test_transfer_category_default(self):
        ftt = FileTransferTokenFactory()
        self.cfs.transfer('/less/important.txt', ftt)
        request = self.cfs._transfers.get()
        self.assertEqual(request.file_category,
                         FileTransferToken.FileInfo.Category.results)

    @mock.patch('golem.network.concent.filetransfers.'
                'ConcentFiletransferService.process')
    def test_run_empty(self, process_mock):
        self.cfs._run()
        process_mock.assert_not_called()

    @mock.patch('golem.network.concent.filetransfers.'
                'ConcentFiletransferService.process')
    def test_run(self, process_mock):
        path = '/yeta/nother.file'
        ftt = FileTransferTokenFactory()
        self.cfs.transfer(path, ftt)
        self.cfs._run()
        process_mock.assert_called_once()
        request = process_mock.call_args[0][0]
        self.assertIsInstance(request, filetransfers.ConcentFileRequest)
        self.assertEqual(request.file_path, path)
        self.assertEqual(request.file_transfer_token, ftt)

    @mock.patch('golem.network.concent.filetransfers.'
                'ConcentFiletransferService.upload')
    def test_process_upload(self, upload_mock):
        ftt = FileTransferTokenFactory(upload=True)
        request = ConcentFileRequestFactory(file_transfer_token=ftt)
        self.cfs.process(request)
        upload_mock.assert_called_once_with(request)

    @mock.patch('golem.network.concent.filetransfers.'
                'ConcentFiletransferService.download')
    def test_process_download(self, download_mock):
        ftt = FileTransferTokenFactory(download=True)
        request = ConcentFileRequestFactory(file_transfer_token=ftt)
        self.cfs.process(request)
        download_mock.assert_called_once_with(request)

    @mock.patch('golem.network.concent.filetransfers.'
                'ConcentFiletransferService.upload', mock.Mock())
    def test_process_success(self):
        success = mock.Mock()
        request = ConcentFileRequestFactory(
            file_transfer_token__upload=True,
            success=success,
        )
        self.cfs.process(request)
        success.assert_called_once()

    def test_process_success_no_handler(self):
        rv = 42
        request = ConcentFileRequestFactory(
            file_transfer_token__upload=True,
        )
        with mock.patch('golem.network.concent.filetransfers.'
                        'ConcentFiletransferService.upload',
                        mock.Mock(return_value=mock.Mock(ok=True, text=rv))):
            response = self.cfs.process(request)

        self.assertEqual(response.text, rv)

    @mock.patch('golem.network.concent.filetransfers.'
                'ConcentFiletransferService.upload',
                mock.Mock(side_effect=Exception()))
    def test_process_error(self):
        error = mock.Mock()
        request = ConcentFileRequestFactory(
            file_transfer_token__upload=True,
            error=error,
        )
        self.cfs.process(request)
        error.assert_called_once()

    @mock.patch('golem.network.concent.filetransfers.'
                'ConcentFiletransferService.upload',
                mock.Mock(side_effect=Exception()))
    def test_process_error_no_handler(self):
        request = ConcentFileRequestFactory(
            file_transfer_token__upload=True,
        )
        with self.assertRaises(Exception):
            self.cfs.process(request)

    def _init_uploaded_file(self, filename: str) -> str:
        file = (self.new_path / filename)
        file.write_text('meh')
        return str(file)

    @mock.patch('golem.network.concent.filetransfers.requests.post')
    def test_upload(self, requests_mock):
        path = self._init_uploaded_file('something.good')

        ftt = FileTransferTokenFactory(upload=True)

        request = ConcentFileRequestFactory(
            file_path=path,
            file_transfer_token=ftt,
        )

        upload_address = ftt.storage_cluster_address + 'upload/'
        headers = self._mock_get_auth_headers(ftt)
        headers['Concent-Upload-Path'] = ftt.files[0].get('path')  # noqa pylint:disable=unsubscriptable-object
        headers['Content-Type'] = 'application/octet-stream'

        self.cfs.upload(request)

        requests_mock.assert_called_once()

        args, kwargs = requests_mock.call_args
        self.assertEqual(args, (upload_address, ))
        self.assertIsNotNone(kwargs.get('headers').pop('Concent-Auth'))
        self.assertEqual(kwargs.get('headers'), headers)

    @mock.patch('golem.network.concent.filetransfers.requests.post')
    def test_upload_multiple_files(self, requests_mock):
        path = self._init_uploaded_file('obsta.cles')
        category = FileTransferToken.FileInfo.Category.resources

        ftt = FileTransferTokenFactory(
            files=[
                FileInfoFactory(
                    category=FileTransferToken.FileInfo.Category.results),
                FileInfoFactory(path=path, category=category),
            ],
            upload=True,
        )

        request = ConcentFileRequestFactory(
            file_path=path,
            file_transfer_token=ftt,
            file_category=category,
        )

        self.cfs.upload(request)

        requests_mock.assert_called_once()

        _, kwargs = requests_mock.call_args
        concent_upload_path = kwargs.get('headers').get('Concent-Upload-Path')
        self.assertEqual(concent_upload_path, ftt.files[1].get('path'))  # noqa pylint:disable=unsubscriptable-object

    @mock.patch('golem.network.concent.filetransfers.requests.get')
    def test_download(self, requests_mock):
        path = self.path + '/gotwell.soon'

        ftt = FileTransferTokenFactory(download=True)

        request = ConcentFileRequestFactory(
            file_path=path,
            file_transfer_token=ftt,
        )

        download_address = ftt.storage_cluster_address + 'download/' + \
            ftt.files[0].get('path')  # noqa pylint:disable=unsubscriptable-object

        self.cfs.download(request)

        requests_mock.assert_called_once()

        args, kwargs = requests_mock.call_args
        self.assertEqual(args, (download_address, ))
        self.assertIsNotNone(kwargs.get('headers').pop('Concent-Auth'))
        self.assertEqual(
            kwargs.get('headers'),
            self._mock_get_auth_headers(ftt)
        )

    @mock.patch('golem.network.concent.filetransfers.requests.get')
    def test_download_multiple_files(self, requests_mock):
        path = self.path + '/spanish.sahara'
        category = FileTransferToken.FileInfo.Category.resources
        ftt = FileTransferTokenFactory(
            files=[
                FileInfoFactory(
                    category=FileTransferToken.FileInfo.Category.results),
                FileInfoFactory(category=category),
            ],
            download=True,
        )

        request = ConcentFileRequestFactory(
            file_path=path,
            file_transfer_token=ftt,
            file_category=category,
        )

        download_address = ftt.storage_cluster_address + 'download/' + \
            ftt.files[1].get('path')  # noqa pylint:disable=unsubscriptable-object

        self.cfs.download(request)

        requests_mock.assert_called_once()
        self.assertEqual(requests_mock.call_args[0], (download_address, ))
