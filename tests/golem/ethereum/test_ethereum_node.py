from unittest.mock import patch, Mock
from unittest import TestCase

from golem.ethereum.node import NodeProcess


class TestPublicNodeList(TestCase):

    def test_node_start(self):
        node = NodeProcess(['addr1', 'addr2'])
        node.web3 = Mock()
        node.is_connected = Mock()
        node._handle_remote_rpc_provider_failure = Mock()

        assert node.addr_list is None
        node.start()
        assert node.addr_list
        assert node.is_connected.called

    @patch('golem.core.async.async_run',
           side_effect=lambda r, *_: r.method(*r.args, **r.kwargs))
    def test_handle_remote_rpc_provider(self, _async_run):
        node = NodeProcess(['addr'])
        node.start = Mock()

        assert node.provider_proxy
        assert node.initial_addr_list
        assert node.addr_list is None

        node.provider_proxy.provider = Mock()
        node.addr_list = []
        node._handle_remote_rpc_provider_failure()

        assert node.provider_proxy.provider is None
        assert node.start.called
