import unittest

from mock import MagicMock, patch

from golem.network.p2p.p2pservice import P2PService
from golem.network.p2p.node import Node
from golem.core.keysauth import EllipticalKeysAuth
from golem.clientconfigdescriptor import ClientConfigDescriptor


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






