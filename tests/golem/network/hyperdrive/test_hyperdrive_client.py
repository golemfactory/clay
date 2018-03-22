import json
import uuid
from unittest import mock, TestCase, skip

from requests import HTTPError
from twisted.internet.defer import Deferred
from twisted.python import failure

from golem.network.hyperdrive.client import HyperdriveAsyncClient, \
    HyperdriveClient, HyperdriveClientOptions

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

    def test_build_options(self, _):
        options = HyperdriveClient.build_options()
        assert options.client_id == HyperdriveClient.CLIENT_ID
        assert options.version == HyperdriveClient.VERSION
        assert options.options['peers'] is None

    def test_id(self, _):
        client = HyperdriveClient()
        result = client.id()
        assert result['id'] == response['id']
        assert result['version'] == response['version']

    def test_addresses(self, _):
        client = HyperdriveClient()
        assert client.addresses() == dict(TCP=('0.0.0.0', 3282))

    def test_add(self, _):
        client = HyperdriveClient()
        assert client.add(response['files']) == response['hash']

    def test_restore(self, _):
        client = HyperdriveClient()
        assert client.restore(response['files']) == response['hash']

    def test_get(self, _):
        client = HyperdriveClient()
        content_hash = str(uuid.uuid4())
        filepath = str(uuid.uuid4())

        with self.assertRaises(KeyError):
            client.get(content_hash)

        assert client.get(content_hash, client_options=None, filepath=filepath)\
            == [(filepath, content_hash, response['files'])]

    def test_cancel(self, _):
        client = HyperdriveClient()
        content_hash = str(uuid.uuid4())
        response_hash = response['hash']
        assert client.cancel(content_hash) == response_hash

    @mock.patch('json.loads')
    @mock.patch('requests.post')
    def test_request(self, post, json_loads, _):
        client = HyperdriveClient()
        resp = mock.Mock()
        post.return_value = resp

        client._request(key="value")
        assert json_loads.called

    @mock.patch('json.loads')
    def test_request_exception(self, json_loads, post):
        client = HyperdriveClient()
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
        client = HyperdriveClient()
        resp = mock.Mock()
        post.return_value = resp

        exception = HTTPError()
        resp.raise_for_status.side_effect = exception

        with self.assertRaises(HTTPError) as exc:
            client._request(key="value")

        assert exc.exception is not exception
        assert not json_loads.called


class TestHyperdriveClientAsync(TestCase):

    @staticmethod
    def success(*_):
        d = Deferred()
        d.callback(mock.Mock(code=200))
        return d

    @staticmethod
    def failure(*_):
        d = Deferred()
        d.errback(Exception())
        return d

    @staticmethod
    @mock.patch('golem.core.async.AsyncHTTPRequest.run')
    def test_get_async_run(request_run):
        client = HyperdriveAsyncClient()
        result = client.get_async('resource_hash',
                                  client_options=None,
                                  filepath='.')

        expected_params = client._download_params('resource_hash',
                                                  None, filepath='.')
        expected_params = json.dumps(expected_params).encode('utf-8')

        assert isinstance(result, Deferred)
        request_run.assert_called_with(
            b'POST',
            client._url_bytes,
            client._headers_obj,
            expected_params
        )

    def test_get_async_error(self):
        client = HyperdriveAsyncClient()

        with mock.patch('golem.core.async.AsyncHTTPRequest.run',
                        side_effect=self.failure):

            wrapper = client.get_async('resource_hash',
                                       client_options=None,
                                       filepath='.')
            assert wrapper.called
            assert isinstance(wrapper.result, failure.Failure)

    def test_get_async_body_error(self):
        client = HyperdriveAsyncClient()

        with mock.patch('twisted.web.client.readBody',
                        side_effect=self.failure), \
            mock.patch('golem.core.async.AsyncHTTPRequest.run',
                       side_effect=self.success):

            wrapper = client.get_async('resource_hash',
                                       client_options=None,
                                       filepath='.')
            assert wrapper.called
            assert isinstance(wrapper.result, failure.Failure)

    def test_get_async(self):

        def body(*_):
            d = Deferred()
            d.callback(b'{"files": ["./file"]}')
            return d

        with mock.patch('twisted.web.client.readBody',
                        side_effect=body), \
            mock.patch('golem.core.async.AsyncHTTPRequest.run',
                       side_effect=self.success):

            client = HyperdriveAsyncClient()
            wrapper = client.get_async('resource_hash',
                                       client_options=None,
                                       filepath='.')
            assert wrapper.called
            assert isinstance(wrapper.result, list)

    def test_add_async(self):

        def body(*_):
            d = Deferred()
            d.callback(b'{"hash": "0a0b0c0d"}')
            return d

        files = {'path/to/file': 'file'}

        with mock.patch('twisted.web.client.readBody',
                        side_effect=body), \
            mock.patch('golem.core.async.AsyncHTTPRequest.run',
                       side_effect=self.success):

            client = HyperdriveAsyncClient()
            wrapper = client.add_async(files)
            assert wrapper.called
            assert isinstance(wrapper.result, str)


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
