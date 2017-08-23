import unittest
import uuid

import mock

from golem.network.hyperdrive.client import HyperdriveClient, \
    HyperdriveClientOptions


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
        assert options.options['peers'] is None

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


class TestHyperdriveClientOptions(unittest.TestCase):

    def test_clone(self):
        peers = [dict(
            TCP=dict(
                address='192.168.1.2',
                port=3282
            ),
            uTP=dict(
                address='192.168.1.2',
                port=3283
            )
        )]

        options = HyperdriveClientOptions('client_id', 1.0,
                                          options=dict(peers=peers))

        cloned = options.clone()
        assert cloned is not options
        assert cloned.client_id == options.client_id
        assert cloned.version == options.version
        assert cloned.options == options.options
        assert cloned.options is not options.options

    def test_filtered(self):
        peers = [
            dict(
                TCP=dict(
                    address='1.2.3.4',
                    port=3282
                ),
                uTP=dict(
                    address='::1.2.3.4',
                    port=3283
                )
            ),
        ]

        client = HyperdriveClient.CLIENT_ID
        version = HyperdriveClient.VERSION

        options = HyperdriveClientOptions(client, version,
                                          options=dict(peers=None))

        assert options.filtered(client, version) is None
        assert options.filtered() is None

        options = HyperdriveClientOptions(client, version,
                                          options=dict(peers=peers))
        filtered = options.filtered()

        assert isinstance(filtered, HyperdriveClientOptions)
        assert filtered.options['peers'] == peers
        assert options.filtered('invalid client', version) is None

    def test_filter_peers(self):
        peers_local_ip = [
            dict(
                TCP=dict(address='192.168.1.2', port=3282),
                uTP=dict(address='192.168.1.2', port=3283)
            ),
            dict(
                TCP=dict(address='::1', port=3282),
                uTP=dict(address='127.0.0.1', port=3283)
            ),
        ]
        peers_remote_ip = [
            dict(
                TCP=dict(address='1.2.3.4', port=3282),
                uTP=dict(address='::1.2.3.4', port=3283)
            )
        ]
        peers_mixed_ip = [
            dict(
                TCP=dict(address='1.2.3.4', port=3282),
                uTP=dict(address='127.0.0.1', port=3283)
            )
        ]

        filtered = HyperdriveClientOptions.filter_peers(
            peers_local_ip + peers_remote_ip)
        assert filtered == peers_remote_ip

        filtered = HyperdriveClientOptions.filter_peers(
            peers_mixed_ip)
        assert filtered == [dict(TCP=dict(address='1.2.3.4', port=3282))]


