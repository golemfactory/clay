import json
import uuid
from unittest import mock, TestCase, skip

from requests import HTTPError
from twisted.internet.defer import Deferred
from twisted.python import failure

from golem.network.hyperdrive.client import HyperdriveAsyncClient, \
    HyperdriveClient, HyperdriveClientOptions

from tests.factories.hyperdrive import hyperdrive_client_kwargs


response = {
    'id': str(uuid.uuid4()),
    'version': '0.2.4',
    'files': ['file1', 'file2'],
    'hash': str(uuid.uuid4()),
    'addresses': dict(
        TCP=dict(address='0.0.0.0', port=3282)
    )
}
response_str = json.dumps(response)


@mock.patch('golem.network.hyperdrive.client.requests.post',
            return_value=mock.Mock(text=response_str,
                                   content=response_str.encode()))
class TestHyperdriveClient(TestCase):

    def setUp(self) -> None:
        self.client_options = HyperdriveClientOptions(
            HyperdriveClient.CLIENT_ID,
            HyperdriveClient.VERSION,
        )
        self.client_options.set(timeout=10., size=1024)

    @staticmethod
    def get_client():
        return HyperdriveClient(**hyperdrive_client_kwargs(wrapped=False))

    def test_build_options(self, _):
        options = HyperdriveClient.build_options()
        assert options.client_id == HyperdriveClient.CLIENT_ID
        assert options.version == HyperdriveClient.VERSION
        assert 'peers' not in options.options

    def test_id(self, _):
        client = self.get_client()
        result = client.id()
        assert result['id'] == response['id']
        assert result['version'] == response['version']

    def test_addresses(self, _):
        client = self.get_client()
        assert client.addresses() == dict(TCP=('0.0.0.0', 3282))

    def test_add(self, _):
        client = self.get_client()
        result = client.add(
            response['files'],
            client_options=self.client_options)
        assert result == response['hash']

    def test_restore(self, _):
        client = self.get_client()
        result = client.restore(
            response['files'],
            client_options=self.client_options)
        assert result == response['hash']

    def test_get(self, _):
        client = self.get_client()
        content_hash = str(uuid.uuid4())
        filepath = str(uuid.uuid4())

        with self.assertRaises(KeyError):
            client.get(content_hash)

        result = client.get(
            content_hash,
            client_options=self.client_options,
            filepath=filepath)
        assert result == [(filepath, content_hash, response['files'])]

    def test_cancel(self, _):
        client = self.get_client()
        content_hash = str(uuid.uuid4())
        response_hash = response['hash']
        assert client.cancel(content_hash) == response_hash

    @mock.patch('json.loads')
    @mock.patch('requests.post')
    def test_request(self, post, json_loads, _):
        client = self.get_client()
        resp = mock.Mock()
        post.return_value = resp

        client._request(key="value")
        assert json_loads.called

    @mock.patch('json.loads')
    def test_request_exception(self, json_loads, post):
        client = self.get_client()
        resp = mock.Mock()
        post.return_value = resp

        exception = Exception()
        resp.raise_for_status.side_effect = exception

        with self.assertRaises(Exception) as exc:
            client._request(key="value")

        assert exc.exception is exception
        assert not json_loads.called

    @mock.patch('json.loads')
    def test_request_http_error(self, json_loads, post):
        client = self.get_client()
        resp = mock.Mock()
        post.return_value = resp

        exception = HTTPError()
        resp.raise_for_status.side_effect = exception

        with self.assertRaises(HTTPError) as exc:
            client._request(key="value")

        assert exc.exception is not exception
        assert not json_loads.called


class TestHyperdriveClientAsync(TestCase):

    def setUp(self) -> None:
        self.client_options = HyperdriveClientOptions(
            HyperdriveClient.CLIENT_ID,
            HyperdriveClient.VERSION,
        )
        self.client_options.set(timeout=10., size=1024)

    @staticmethod
    def get_client():
        return HyperdriveAsyncClient(**hyperdrive_client_kwargs(wrapped=False))

    @mock.patch('golem.core.golem_async.AsyncHTTPRequest.run')
    def test_get_async_run(self, request_run):
        client = TestHyperdriveClientAsync.get_client()
        result = client.get_async(
            'resource_hash',
            client_options=self.client_options,
            filepath='.')

        expected_params = client._download_params(
            'resource_hash',
            client_options=self.client_options,
            filepath='.')
        expected_params = json.dumps(expected_params).encode(client.ENCODING)
        uri = f'{client._url}/{client.DEFAULT_ENDPOINT}'.encode(client.ENCODING)

        assert isinstance(result, Deferred)
        request_run.assert_called_with(
            b'POST',
            uri=uri,
            headers=client.RAW_HEADERS,
            body=expected_params,
        )


class TestHyperdriveClientOptions(TestCase):

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
                TCP=('1.2.3.4', 3282)
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

    @skip('Private IP filtering is temporarily disabled')
    def test_filter_peers(self):
        peers_local = [
            dict(
                TCP=('192.168.1.2', 3282)
            ),
            dict(
                TCP=('::1', 3282)
            )
        ]
        peers_remote = [
            dict(
                TCP=('1.2.3.4', 3282)
            )
        ]
        peers_mixed = [
            dict(
                TCP=('1.2.3.4', 3282)
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

        valid_addresses = dict(
            TCP=valid_v4
        )

        assert HyperdriveClientOptions.filter_peer(dict(
            TCP=(None, 12345),
            uTP=('test string', 12345)
        )) == {}

        assert HyperdriveClientOptions.filter_peer(dict(
            TCP=('192.168.0.1', 12345),
            uTP=('::1', 12345)
        )) != {}

        assert HyperdriveClientOptions.filter_peer(dict(
            TCP=('::1.2.3.4', -1),
            uTP=('1.2.3.4', None)
        )) == {}

        assert HyperdriveClientOptions.filter_peer(dict(
            TCP=(None, 12345),
            uTP=valid_v4
        )) == {}

        assert HyperdriveClientOptions.filter_peer(dict(
            TCP=('1.2.3.4', 1234),
            uTP=valid_v4
        )) == dict(TCP=valid_v4)

        assert HyperdriveClientOptions.filter_peer(
            valid_addresses) == valid_addresses
