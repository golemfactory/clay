import time
import unittest

from golem.network.transport.tcpnetwork import SocketAddress
from mock import MagicMock

from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.keysauth import EllipticalKeysAuth
from golem.network.p2p.node import Node
from golem.network.p2p.p2pservice import P2PService


class TestP2PService(unittest.TestCase):
    def test_add_to_peer_keeper(self):
        keys_auth = EllipticalKeysAuth()
        service = P2PService(None, ClientConfigDescriptor(), keys_auth)
        node = Node()
        node.key = EllipticalKeysAuth("TEST").get_key_id()
        m_test2 = MagicMock()
        m_test3 = MagicMock()
        service.peers["TEST3"] = m_test3
        service.peers["TEST2"] = m_test2
        service.peer_keeper = MagicMock()
        node2 = Node()
        node2.key = "TEST2"
        service.peer_keeper.add_peer = MagicMock(return_value=node2)
        service.add_to_peer_keeper(node)
        m_test2.ping.assert_called_with(0)
        m_test3.ping.assert_not_called()
        for i in range(100):
            service.peers[str(i)] = MagicMock()
        node2.key = "59"
        service.add_to_peer_keeper(node)
        service.peers["59"].ping.assert_called_with(0)
        for i in range(58) + range(60, 100):
            service.peers[str(i)].ping.assert_not_called()
        node2.key = None
        service.add_to_peer_keeper(node)
        for i in range(58) + range(60, 100):
            service.peers[str(i)].ping.assert_not_called()
        service.peers["59"].ping.assert_called_once_with(0)
        m_test2.ping.assert_called_once_with(0)
        m_test3.ping.assert_not_called()
        self.assertEqual(len(service.peers), 102)

    def test_remove_old_peers(self):
        keys_auth = EllipticalKeysAuth()
        service = P2PService(None, ClientConfigDescriptor(), keys_auth)
        node = MagicMock()
        node.key = EllipticalKeysAuth("TEST").get_key_id()
        node.key_id = node.key

        service.last_peers_request = time.time() + 10
        service.add_peer(node.key, node)
        assert len(service.peers) == 1
        node.last_message_time = 0
        service.sync_network()
        assert len(service.peers) == 0

        service.add_peer(node.key, node)
        service.peers[node.key].last_message_time = time.time() + 1000
        assert len(service.peers) == 1
        service.sync_network()
        assert len(service.peers) == 1

    def test_refresh_peers(self):
        keys_auth = EllipticalKeysAuth()
        service = P2PService(None, ClientConfigDescriptor(), keys_auth)
        sa = SocketAddress('127.0.0.1', 11111)

        node = MagicMock()
        node.key = EllipticalKeysAuth("TEST").get_key_id()
        node.key_id = node.key
        node.address = sa

        node2 = MagicMock()
        node2.key = EllipticalKeysAuth("TEST2").get_key_id()
        node2.key_id = node2.key
        node2.address = sa

        service.add_peer(node.key, node)
        service.add_peer(node2.key, node2)

        service.peers[node.key].last_message_time = time.time() + 1000
        service.peers[node2.key].last_message_time = time.time() + 1000

        service.config_desc.opt_peer_num = 1000

        assert len(service.peers) == 2
        service.sync_network()
        assert len(service.peers) == 2

        service.last_refresh_peers = 0
        service.last_peers_request = 0
        service._peer_dbg_time_threshold = 0
        service.sync_network()
        assert len(service.peers) == 1

    def test_redundant_peers(self):
        keys_auth = EllipticalKeysAuth()
        service = P2PService(None, ClientConfigDescriptor(), keys_auth)
        sa = SocketAddress('127.0.0.1', 11111)

        node = MagicMock()
        node.key = EllipticalKeysAuth("TEST").get_key_id()
        node.key_id = node.key
        node.address = sa

        service.config_desc.opt_peer_num = 0
        service.add_peer(node.key, node)

        assert len(service.redundant_peers()) == 1
        assert service.enough_peers()

    def test_sync_free_peers(self):
        keys_auth = EllipticalKeysAuth()
        service = P2PService(None, ClientConfigDescriptor(), keys_auth)

        node = MagicMock()
        node.key = EllipticalKeysAuth("TEST").get_key_id()
        node.key_id = node.key
        node.pub_addr = '127.0.0.1'
        node.pub_port = 10000

        service.config_desc.opt_peer_num = 10
        service.free_peers.append(node.key)
        service.incoming_peers[node.key] = {
            'address': '127.0.0.1',
            'port': 10000,
            'node': node,
            'node_name': 'TEST',
            'conn_trials': 0
        }

        service.sync_network()

        assert not service.free_peers
        assert len(service.pending_connections) == 1
