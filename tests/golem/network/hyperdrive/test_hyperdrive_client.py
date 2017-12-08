import unittest
import uuid

import mock

from golem.network.hyperdrive.client import HyperdriveClient, \
    HyperdriveClientOptions


class TestHyperdriveClient(unittest.TestCase):

    def setUp(self):
        self.response = {
            'id': str(uuid.uuid4()),
            'files': ['file1', 'file2'],
            'hash': str(uuid.uuid4()),
            'addresses': dict(
                TCP=dict(address='0.0.0.0', port=3282)
            )
        }

    def test_build_options(self):
        options = HyperdriveClient.build_options()
        assert options.client_id == HyperdriveClient.CLIENT_ID
        assert options.version == HyperdriveClient.VERSION
        assert options.options['peers'] is None

    def test_diagnostics(self):
        client = HyperdriveClient()

        with self.assertRaises(NotImplementedError):
            client.diagnostics()

    def test_id(self):
        client = HyperdriveClient()

        with mock.patch.object(HyperdriveClient, '_request',
                               return_value=self.response):
            assert client.id() == self.response['id']

    def test_addresses(self):
        client = HyperdriveClient()

        with mock.patch.object(HyperdriveClient, '_request',
                               return_value=self.response):
            assert client.addresses() == dict(TCP=('0.0.0.0', 3282))

    def test_add(self):
        client = HyperdriveClient()

        with mock.patch.object(HyperdriveClient, '_request',
                               return_value=self.response):
            assert client.add(self.response['files']) == self.response['hash']

    def test_restore(self):
        client = HyperdriveClient()

        with mock.patch.object(HyperdriveClient, '_request',
                               return_value=self.response):
            assert client.restore(self.response['files']) == \
                   self.response['hash']

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
        peers = [
            dict(
                TCP=('192.168.1.2', 3282),
                uTP=('192.168.1.2', 3283)
            )
        ]

        options = HyperdriveClientOptions('client_id', 1.0,
                                          options=dict(peers=peers))

        cloned = options.clone()
        # Assert that cloned is a different object
        assert cloned is not options
        assert cloned.options is not options.options
        # Assert property equality
        assert cloned.client_id == options.client_id
        assert cloned.version == options.version
        assert cloned.options == options.options

    def test_filtered(self):
        peers = [
            dict(
                TCP=('1.2.3.4', 3282),
                uTP=('::1.2.3.4', 3283)
            )
        ]

        client = HyperdriveClient.CLIENT_ID
        version = HyperdriveClient.VERSION

        # Invalid client
        options = HyperdriveClientOptions('some_client', version,
                                          options=dict(peers=None))
        assert options.filtered(client, version) is None
        assert options.filtered() is None

        # Invalid version
        options = HyperdriveClientOptions(client, 0.0,
                                          options=dict(peers=peers))
        assert options.filtered(client, version) is None
        assert options.filtered() is None

        # Empty peers
        options = HyperdriveClientOptions(client, version,
                                          options=dict(peers=None))
        assert options.filtered(client, version) is None
        assert options.filtered() is None

        # Valid arguments
        options = HyperdriveClientOptions(client, version,
                                          options=dict(peers=peers))
        filtered = options.filtered()

        assert isinstance(filtered, HyperdriveClientOptions)
        assert filtered.options['peers'] == peers
        assert options.filtered('invalid client', version) is None

    @unittest.skip('Private IP filtering is temporarily disabled')
    def test_filter_peers(self):
        peers_local = [
            dict(
                TCP=('192.168.1.2', 3282),
                uTP=('192.168.1.2', 3283)
            ),
            dict(
                TCP=('::1', 3282),
                uTP=('127.0.0.1', 3283)
            )
        ]
        peers_remote = [
            dict(
                TCP=('1.2.3.4', 3282),
                uTP=('::1.2.3.4', 3283)
            )
        ]
        peers_mixed = [
            dict(
                TCP=('1.2.3.4', 3282),
                uTP=('127.0.0.1', 3283)
            )
        ]

        filtered = HyperdriveClientOptions.filter_peers(
            peers_local + peers_remote + [{}])
        assert filtered == peers_remote

        filtered = HyperdriveClientOptions.filter_peers(
            peers_mixed)
        assert filtered == [dict(TCP=('1.2.3.4', 3282))]

        filtered = HyperdriveClientOptions.filter_peers(
            peers_remote + peers_mixed)
        assert len(filtered) == 2

        with mock.patch.object(HyperdriveClientOptions, 'max_peers', 1):
            filtered = HyperdriveClientOptions.filter_peers(
                peers_remote + peers_mixed)
            assert len(filtered) == 1

    def test_filter_peer(self):
        valid_v4 = ('1.2.3.4', 1234)
        valid_v6 = ('::1.2.3.4', 1234)

        valid_addresses = dict(
            TCP=valid_v4,
            uTP=valid_v6
        )

        assert HyperdriveClientOptions.filter_peer(dict(
            TCP=(None, 12345),
            uTP=('test string', 12345)
        )) is None

        assert HyperdriveClientOptions.filter_peer(dict(
            TCP=('192.168.0.1', 12345),
            uTP=('::1', 12345)
        )) is not None

        assert HyperdriveClientOptions.filter_peer(dict(
            TCP=('::1.2.3.4', -1),
            uTP=('1.2.3.4', None)
        )) is None

        assert HyperdriveClientOptions.filter_peer(dict(
            TCP=(None, 12345),
            uTP=valid_v4
        )) == dict(uTP=valid_v4)

        assert HyperdriveClientOptions.filter_peer(dict(
            TCP=(None, 12345),
            uTP=valid_v4
        ), excluded_ips=['1.2.3.4']) is None

        assert HyperdriveClientOptions.filter_peer(
            valid_addresses, forced_ip='2.3.4.5'
        ) == dict(
            TCP=('2.3.4.5', 1234),
            uTP=('2.3.4.5', 1234)
        )

        assert HyperdriveClientOptions.filter_peer(
            valid_addresses) == valid_addresses
