import factory

from golem_messages.factories.concents import FileTransferTokenFactory

from golem.network.concent import filetransfers



class ConcentFileRequestFactory(factory.Factory):
    class Meta:
        model = filetransfers.ConcentFileRequest

    file_path = factory.Faker('file_path')
    file_transfer_token = factory.SubFactory(FileTransferTokenFactory)
