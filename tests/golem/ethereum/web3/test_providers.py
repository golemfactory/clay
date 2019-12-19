# pylint: disable=protected-access
import datetime
import time
from unittest import TestCase
from unittest.mock import patch, Mock

import freezegun

from golem.ethereum.web3.providers import (
    ProviderProxy,
    RETRY_COUNT_INTERVAL,
    SINGLE_QUERY_RETRY_LIMIT,
)


@patch('web3.providers.rpc.HTTPProvider')
class TestProviders(TestCase):
    def setUp(self):
        self._nodes_list = ['http://golem', 'http://melog']
        self.proxy = ProviderProxy(self._nodes_list)
        self.provider = Mock()

    def test_successful_calls(self, *_):
        self.proxy.provider.make_request = Mock(return_value="Working")

        result = self.proxy.make_request("a", [])

        self.assertEqual(result, "Working")
        self.proxy.provider.make_request.assert_called_once_with("a", [])

    def test_recoverable_errors(self, *_):
        self.proxy.provider.make_request = Mock(side_effect=[None, "Working"])

        result = self.proxy.make_request("a", [])

        self.assertEqual(result, "Working")
        self.proxy.provider.make_request.assert_called_with("a", [])
        self.assertEqual(self.proxy.provider.make_request.call_count, 2)

    @patch(
        'golem.ethereum.web3.providers.HTTPProvider.make_request',
        Mock(side_effect=ConnectionError()))
    def test_unrecoverable_errors(self, *_):
        result = None
        with self.assertRaises(Exception):
            result = self.proxy.make_request("a", [])

        self.assertEqual(result, None)
        self.proxy.provider.make_request.assert_called_with("a", [])
        self.assertEqual(
            self.proxy.provider.make_request.call_count,
            SINGLE_QUERY_RETRY_LIMIT * len(self._nodes_list)
        )

    @patch(
        'golem.ethereum.web3.providers.HTTPProvider.make_request',
        side_effect=ValueError({
            'code': -32000,
            'message': 'missing trie node 32de5daba1d1013d41aca01c66772685576afb925779aa35d4d5a9de6e41d8c0 (path )',  # noqa pylint: disable=line-too-long
        }),
    )
    def test_non_connection_error(self, *_):
        result = None
        with self.assertRaises(ValueError):
            result = self.proxy.make_request("a", [])

        self.assertEqual(result, None)
        self.proxy.provider.make_request.assert_called_once_with("a", [])
        self.assertEqual(
            self.proxy.provider.make_request.call_count,
            1,
        )

    def test_first_retry(self, *_):
        with freezegun.freeze_time(datetime.datetime.utcnow()):
            now = time.time()
            self.proxy._register_retry()

        self.assertEqual(self.proxy._first_retry_time, now)
        self.assertEqual(self.proxy._retries, 1)

    def test_subsequent_retry(self, *_):
        with freezegun.freeze_time(datetime.datetime.utcnow()):
            frt = time.time() - RETRY_COUNT_INTERVAL / 2
            self.proxy._first_retry_time = frt
            self.proxy._retries = 2
            self.proxy._register_retry()

        self.assertEqual(self.proxy._first_retry_time, frt)
        self.assertEqual(self.proxy._retries, 3)

    def test_subsequent_distant_retry(self, *_):
        with freezegun.freeze_time(datetime.datetime.utcnow()):
            now = time.time()
            frt = now - RETRY_COUNT_INTERVAL - 1
            self.proxy._first_retry_time = frt
            self.proxy._retries = 2
            self.proxy._register_retry()

        self.assertEqual(self.proxy._first_retry_time, now)
        self.assertEqual(self.proxy._retries, 1)
