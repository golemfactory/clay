import factory

from golem.network.concent import filetransfers
from .messages import FileTransferTokenFactory

# pylint:disable=too-few-public-methods


class ConcentFileRequestFactory(factory.Factory):
    class Meta:
        model = filetransfers.ConcentFileRequest

    file_path = factory.Faker('file_path')
    file_transfer_token = factory.SubFactory(FileTransferTokenFactory)
