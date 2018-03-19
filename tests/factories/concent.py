import factory

from golem.network.concent import filetransfers
from .messages import FileTransferTokenFactory


class ConcentFileRequestFactory(factory.Factory):
    class Meta:
        model = filetransfers.ConcentFileRequest

    file_path = factory.Faker('file_path')
    file_transfer_token = factory.SubFactory(FileTransferTokenFactory)
