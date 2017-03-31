import unittest
import uuid

import mock

from golem.network.hyperdrive.client import HyperdriveClient


class TestHyperdriveClient(unittest.TestCase):

    def setUp(self):
        self.response = {
            'files': [
                'file1', 'file2'
            ],
            'hash': str(uuid.uuid4())
        }

    def test_build_options(self):
        node_id = str(uuid.uuid4())
        options = HyperdriveClient.build_options(node_id)
        assert options.client_id == HyperdriveClient.CLIENT_ID
        assert options.version == HyperdriveClient.VERSION
        assert not options.options

    def test_diagnostics(self):
        client = HyperdriveClient()

        with self.assertRaises(NotImplementedError):
            client.diagnostics()

    def test_add(self):
        client = HyperdriveClient()

        with mock.patch.object(HyperdriveClient, '_request',
                               return_value=self.response):
            assert client.add(self.response['files']) == self.response['hash']

    def test_get_file(self):
        client = HyperdriveClient()
        multihash = str(uuid.uuid4())
        filepath = str(uuid.uuid4())

        with mock.patch.object(HyperdriveClient, '_request',
                               return_value=self.response):

            with self.assertRaises(KeyError):
                client.get_file(multihash)

            assert client.get_file(multihash,
                                   client_options=None,
                                   filepath=filepath) == \
                [(filepath, multihash, self.response['files'])]

    def test_pin_add(self):
        client = HyperdriveClient()
        multihash = str(uuid.uuid4())
        filepath = str(uuid.uuid4())

        with mock.patch.object(HyperdriveClient, '_request',
                               return_value=self.response):

            assert client.pin_add(filepath, multihash) == self.response['hash']

    def test_pin_rm(self):
        client = HyperdriveClient()
        multihash = str(uuid.uuid4())
        with mock.patch.object(HyperdriveClient, '_request',
                               return_value=self.response):

            assert client.pin_rm(multihash) == self.response['hash']


