import base64
import logging
import typing
import queue

import requests

import golem_messages
from golem_messages.message.concents import (
    FileTransferToken, ClientAuthorization
)

from golem import constants as gconst
from golem.core import keysauth
from golem.core.service import LoopingCallService

from .helpers import ssl_kwargs

logger = logging.getLogger(__name__)


class ConcentFileRequest:
    def __init__(self,  # noqa pylint:disable=too-many-arguments
                 file_path: str,
                 file_transfer_token: FileTransferToken,
                 success: typing.Optional[typing.Callable] = None,
                 error: typing.Optional[typing.Callable] = None,
                 file_category: typing.Optional[
                     FileTransferToken.FileInfo.Category] = None) -> None:  # noqa pylint:disable=bad-whitespace
        self.file_path = file_path
        self.file_transfer_token = file_transfer_token
        self.success = success
        self.error = error
        self.file_category = file_category or \
            FileTransferToken.FileInfo.Category.results

    def __repr__(self):
        return '%s request - path: %r, ftt: %r, category: %r' % (
            self.file_transfer_token.operation.value,
            self.file_path,
            self.file_transfer_token,
            self.file_category,
        )


class ConcentFiletransferError(Exception):
    pass


class ConcentFiletransferService(LoopingCallService):
    """
    Golem service responsible for exchanging files with the Concent service.
    """

    def __init__(self,
                 keys_auth: keysauth.KeysAuth,
                 variant: dict,
                 interval_seconds: int = 1,) -> None:
        # SEE golem.core.variables.CONCENT_CHOICES
        self.variant = variant
        self.keys_auth = keys_auth
        self._transfers: queue.Queue = queue.Queue()
        super().__init__(interval_seconds=interval_seconds)

    def start(self, now: bool = True):
        super().start(now=now)
        logger.debug("Concent Filetransfer Service started")

    def stop(self):
        self._transfers.join()
        super().stop()
        logger.debug("Concent Filetransfer Service stopped")

    def transfer(self,  # noqa pylint:disable=too-many-arguments
                 file_path: str,
                 file_transfer_token: FileTransferToken,
                 success: typing.Optional[typing.Callable] = None,
                 error: typing.Optional[typing.Callable] = None,
                 file_category: typing.Optional[
                     FileTransferToken.FileInfo.Category] = None) -> None:  # noqa pylint:disable=bad-whitespace

        if not self.running:
            logger.warning("Request scheduled when service is not started")

        request = ConcentFileRequest(
            file_path, file_transfer_token,
            success=success, error=error, file_category=file_category)

        logger.debug("Scheduling: %r", request)
        self._transfers.put(request)

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
            else:
                response = self.download(request)
            if not response.ok:
                raise ConcentFiletransferError(
                    '{}: {}'.format(response.status_code, response.text))
        except Exception as e:  # noqa pylint:disable=broad-except
            if request.error:
                request.error(e)
                return None
            else:
                raise e

        return request.success(response) if request.success else response

    @staticmethod
    def _get_upload_uri(file_transfer_token: FileTransferToken):
        return '{}upload/'.format(
            file_transfer_token.storage_cluster_address)

    @staticmethod
    def _get_download_uri(file_transfer_token: FileTransferToken,
                          file_category: FileTransferToken.FileInfo.Category):
        return '{}{}{}'.format(
            file_transfer_token.storage_cluster_address,
            'download/',
            file_transfer_token.get_file_info(file_category).get('path')
        )

    def _get_auth_headers(self, file_transfer_token: FileTransferToken):
        auth_key = base64.b64encode(file_transfer_token.serialize()).decode()
        auth_data = base64.b64encode(
            golem_messages.dump(
                ClientAuthorization(
                    client_public_key=self.keys_auth.public_key
                ),
                self.keys_auth._private_key, self.variant['pubkey']  # noqa pylint:disable=protected-access
            )
        ).decode()

        logger.debug(
            "Generating headers - ftt: %s, auth: %s, concent_auth: %s",
            file_transfer_token, auth_key, auth_data)

        return {
            'Authorization': 'Golem ' + auth_key,
            'Concent-Auth': auth_data,
            'X-Golem-Messages': str(gconst.GOLEM_MESSAGES_VERSION),
        }

    def upload(self, request: ConcentFileRequest):
        uri = self._get_upload_uri(request.file_transfer_token)
        ftt = request.file_transfer_token
        headers = self._get_auth_headers(ftt)
        path = ftt.get_file_info(request.file_category).get('path')
        headers.update({
            'Concent-Upload-Path': path,
            'Content-Type': 'application/octet-stream',
        })

        logger.debug("Uploading file '%s' to '%s' using %s",
                     request.file_path, uri, headers)

        with open(request.file_path, mode='rb') as f:
            response = requests.post(
                uri, data=f, headers=headers, **ssl_kwargs(self.variant))
        return response

    def download(self, request: ConcentFileRequest):
        uri = self._get_download_uri(request.file_transfer_token,
                                     request.file_category)
        headers = self._get_auth_headers(request.file_transfer_token)
        response = requests.get(
            uri, stream=True, headers=headers, **ssl_kwargs(self.variant))
        with open(request.file_path, mode='wb') as f:
            for chunk in response.iter_content(chunk_size=None):
                f.write(chunk)
        return response
