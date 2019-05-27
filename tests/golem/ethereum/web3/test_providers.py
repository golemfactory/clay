from unittest import TestCase
from unittest.mock import patch, Mock

from golem.ethereum.web3.providers import ProviderProxy


@patch('web3.providers.rpc.HTTPProvider')
class TestProviders(TestCase):

    def test_successful_calls(self, *_):
        proxy = ProviderProxy(['http://golem'])
        proxy.provider = Mock()
        proxy.provider.make_request = Mock(return_value="Working")

        result = proxy.make_request("a", [])

        self.assertEqual(result, "Working")
        proxy.provider.make_request.assert_called_once_with("a", [])

    def test_recoverable_errors(self, *_):
        proxy = ProviderProxy(['http://golem'])
        proxy.provider = Mock()
        proxy.provider.make_request = Mock(side_effect=[None, "Working"])

        result = proxy.make_request("a", [])

        self.assertEqual(result, "Working")
        proxy.provider.make_request.assert_called_with("a", [])
        self.assertEqual(proxy.provider.make_request.call_count, 2)

    def test_unrecoverable_errors(self, *_):
        proxy = ProviderProxy(['http://golem'])
        proxy.provider = Mock()
        proxy.provider.make_request = Mock(side_effect=ConnectionError())

        result = None
        with self.assertRaises(Exception):
            result = proxy.make_request("a", [])

        self.assertEqual(result, None)
        proxy.provider.make_request.assert_called_with("a", [])
        self.assertEqual(proxy.provider.make_request.call_count, 3)
