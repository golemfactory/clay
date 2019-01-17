from unittest import TestCase
from unittest.mock import patch, Mock

import requests

from golem.ethereum.faucet import tETH_faucet_donate


class FaucetTest(TestCase):
    @classmethod
    @patch('requests.get')
    def test_error_code(cls, get):
        addr = '0x' + 40 * '1'
        response = Mock(spec=requests.Response)
        response.status_code = 500
        get.return_value = response
        assert tETH_faucet_donate(addr) is False

    @classmethod
    @patch('requests.get')
    def test_error_msg(cls, get):
        addr = '0x' + 40 * '1'
        response = Mock(spec=requests.Response)
        response.status_code = 403
        response.json.return_value = {'message': "Ooops!"}
        get.return_value = response
        assert tETH_faucet_donate(addr) is False

    @classmethod
    @patch('requests.get')
    def test_success(cls, get):
        addr = '0x' + 40 * '1'
        response = Mock(spec=requests.Response)
        response.status_code = 200
        response.json.return_value = {'amount': 999999999999999}
        get.return_value = response
        assert tETH_faucet_donate(addr) is True
        assert get.call_count == 1
        assert addr in get.call_args[0][0]
