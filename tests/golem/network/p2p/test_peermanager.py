import copy
import unittest

from ethereum.utils import encode_hex
from mock import Mock, sentinel

from golem.network.p2p.peermanager import GolemPeerManager
from golem.network.p2p.peer import COMPUTATION_CAPABILITY


def _mock_app():
    return Mock(
        config=dict(
            node=dict(
                privkey_hex=encode_hex(b'1' * 32),
                pubkey_hex=encode_hex(b'2' * 32)
            )
        ),
        services=dict()
    )


class TestTaskPeerManagerWrapper(unittest.TestCase):

    def test_computation_capability(self):
        app = _mock_app()

        peer_manager = GolemPeerManager(app)
        self.assertEqual(peer_manager.computation_capability, 0)

        wrapped = copy.copy(peer_manager)
        wrapped.computation_capability = True
        self.assertEqual(wrapped.computation_capability, 1)

        # Make sure that references are intact
        assert wrapped.peers is peer_manager.peers
        assert wrapped.errors is peer_manager.errors
        assert wrapped.server is peer_manager.server


class TestGolemPeerManager(unittest.TestCase):

    def test_hello_received(self):
        app = _mock_app()
        app.config['p2p'] = {'max_peers': 3}

        remote_pubkey = b'3' * 32
        peer = Mock(remote_pubkey=remote_pubkey)
        peer2 = Mock(remote_pubkey=remote_pubkey)
        proto = Mock(peer=peer)

        peer_mgr = GolemPeerManager(app)

        peer_mgr.peers.append(peer)
        self.assertTrue(peer_mgr.on_hello_received(proto, Mock(), Mock(), [],
                                                   Mock(), remote_pubkey))
        proto.send_disconnect.assert_not_called()

        proto.disconnect.reason.already_connected = sentinel.already_connected

        peer_mgr.peers.append(peer2)
        self.assertFalse(peer_mgr.on_hello_received(proto, Mock(), Mock(), [],
                                                    Mock(), remote_pubkey))
        proto.send_disconnect.assert_called_once_with(
            sentinel.already_connected)

        remote_pubkey3 = b'4' * 32
        peer3 = Mock(remote_pubkey=remote_pubkey3)
        proto3 = Mock(peer=peer3)

        peer_mgr.peers.append(peer3)
        self.assertTrue(peer_mgr.on_hello_received(proto3, Mock(), Mock(), [],
                                                   Mock(), remote_pubkey3))
        proto3.send_disconnect.assert_not_called()

        remote_pubkey4 = b'5' * 32
        peer4 = Mock(remote_pubkey=remote_pubkey4)
        proto4 = Mock(peer=peer4)

        proto4.disconnect.reason.too_many_peers = sentinel.too_many_peers

        peer_mgr.peers.append(peer4)
        self.assertFalse(peer_mgr.on_hello_received(proto4, Mock(), Mock(), [],
                                                    Mock(), remote_pubkey4))
        proto4.send_disconnect.assert_called_once_with(
            sentinel.too_many_peers)

        proto4.send_disconnect.reset_mock()

        peer_mgr.peers.append(peer4)
        self.assertTrue(peer_mgr.on_hello_received(
            proto4, Mock(), Mock(), [(COMPUTATION_CAPABILITY, None)],
            Mock(), remote_pubkey4))
        proto3.send_disconnect.assert_not_called()

    def test_disconnect(self):
        def mock_proto(name):
            p = Mock()
            p.name = name
            return p

        p1 = mock_proto("foo")
        p2 = mock_proto("coolprotocol")
        p3 = mock_proto("totally-not-p2p")
        p4_p2p = mock_proto("p2p")
        peer = Mock()
        peer.protocols = [p1, p2, p3]

        reason = "I have a bad day"

        self.assertFalse(GolemPeerManager.disconnect(peer, reason))

        for p in [p1, p2, p3]:
            p.send_disconnect.assert_not_called()
        p4_p2p.send_disconnect.assert_not_called()

        peer.protocols = [p1, p2, p3, p4_p2p]

        self.assertEqual("p2p", p4_p2p.name)

        self.assertTrue(GolemPeerManager.disconnect(peer, reason))

        for p in [p1, p2, p3]:
            p.send_disconnect.assert_not_called()
        p4_p2p.send_disconnect.assert_called_once_with(reason)
