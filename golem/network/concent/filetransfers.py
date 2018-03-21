import base64
import logging
import typing
import queue

import requests

from golem_messages.message.concents import FileTransferToken

from golem.core import keysauth
from golem.core.service import LoopingCallService

logger = logging.getLogger(__name__)


class ConcentFileRequest():  # noqa pylint:disable=too-few-public-methods
    def __init__(self,
                 file_path: str,
                 file_transfer_token: FileTransferToken,
                 success: typing.Optional[typing.Callable] = None,
                 error: typing.Optional[typing.Callable] = None) -> None:
        self.file_path = file_path
        self.file_transfer_token = file_transfer_token
        self.success = success
        self.error = error

    def __repr__(self):
        return '%s request: %r %r' % (
            self.file_transfer_token.operation.value,
            self.file_path,
            self.file_transfer_token)


class ConcentFiletransferService(LoopingCallService):
    """
    Golem service responsible for exchanging files with the Concent service.
    """

    def __init__(self,
                 keys_auth: keysauth.KeysAuth,
                 interval_seconds: int = 1) -> None:
        self.keys_auth = keys_auth
        self._transfers: queue.Queue = queue.Queue()
        super().__init__(interval_seconds=interval_seconds)

    def start(self, now: bool = True):
        super().start(now=now)
        logger.debug("Concent Filestransfer Service started")

    def stop(self):
        self._transfers.join()
        super().stop()
        logger.debug("Concent Filestransfer Service stopped")

    def transfer(self,
                 file_path: str,
                 file_transfer_token: FileTransferToken,
                 success: typing.Optional[typing.Callable] = None,
                 error: typing.Optional[typing.Callable] = None):

        if not self.running:
            logger.warning("Request scheduled when service is not started")

        request = ConcentFileRequest(
            file_path, file_transfer_token, success=success, error=error)

        logger.debug("Scheduling: %r", request)
        return self._transfers.put(request)

    def _run(self):
        try:
            request = self._transfers.get_nowait()
        except queue.Empty:
            return
        self.process(request)
        self._transfers.task_done()

    def process(self, request: ConcentFileRequest):
        logger.debug("Processing: %r", request)
        try:
            if request.file_transfer_token.is_upload:
                response = self.upload(request)
            elif request.file_transfer_token.is_download:
                response = self.download(request)
        except Exception as e:  # noqa pylint:disable=broad-except
            if request.error:
                request.error(e)
                return None
            else:
                raise

        return request.success(response) if request.success else response

    @staticmethod
    def _get_upload_uri(file_transfer_token: FileTransferToken):
        return '{}upload/'.format(
            file_transfer_token.storage_cluster_address)

    @staticmethod
    def _get_download_uri(file_transfer_token: FileTransferToken):
        return '{}{}{}'.format(
            file_transfer_token.storage_cluster_address,
            'download',
            file_transfer_token.files[0].get('path')
        )

    def _get_auth_headers(self, file_transfer_token: FileTransferToken):
        return {
            'Authorization': 'Golem ' + base64.b64encode(
                file_transfer_token.serialize()).decode(),
            'Concent-Client-Public-Key': base64.b64encode(
                self.keys_auth.public_key)
        }

    def upload(self, request):
        uri = self._get_upload_uri(request.file_transfer_token)
        ftt = request.file_transfer_token
        headers = self._get_auth_headers(ftt)
        headers.update({
            'Concent-Upload-Path': ftt.files[0].get('path')
        })
        with open(request.file_path, mode='rb') as f:
            response = requests.post(uri, data=f, headers=headers)
        return response

    def download(self, request):
        uri = self._get_download_uri(request.file_transfer_token)
        headers = self._get_auth_headers(request.file_transfer_token)
        response = requests.get(uri, stream=True, headers=headers)
        with open(request.file_path, mode='wb') as f:
            for chunk in response.iter_content(chunk_size=None):
                f.write(chunk)
        return response
