import unittest
from random import random

from mock import MagicMock

from golem.core.keysauth import EllipticalKeysAuth, KeysAuth
from golem.network.p2p.node import Node
from golem.network.p2p.p2pservice import P2PService
from golem.network.p2p.peersession import PeerSession, logger, P2P_PROTOCOL_ID, PeerSessionInfo
from golem.network.transport.message import MessageHello
from golem.tools.assertlogs import LogTestCase
from golem.tools.testwithappconfig import TestWithKeysAuth


class TestPeerSession(TestWithKeysAuth, LogTestCase):

    def test_init(self):
        ps = PeerSession(MagicMock())
        self.assertIsInstance(ps, PeerSession)

    def test_encrypt_decrypt(self):
        ps = PeerSession(MagicMock())
        ps2 = PeerSession(MagicMock())

        ek = EllipticalKeysAuth(self.path, "RANDOMPRIV", "RANDOMPUB")
        ek2 = EllipticalKeysAuth(self.path, "RANDOMPRIV2", "RANDOMPUB2")
        ps.p2p_service.encrypt = ek.encrypt
        ps.p2p_service.decrypt = ek.decrypt
        ps.key_id = ek2.key_id
        ps2.p2p_service.encrypt = ek2.encrypt
        ps2.p2p_service.decrypt = ek2.decrypt
        ps2.key_id = ek.key_id

        data = "abcdefghijklm" * 1000
        self.assertEqual(ps2.decrypt(ps.encrypt(data)), data)
        self.assertEqual(ps.decrypt(ps2.encrypt(data)), data)
        with self.assertLogs(logger, level=1) as l:
            self.assertEqual(ps2.decrypt(data), data)
        self.assertTrue(any(["not encrypted" in log for log in l.output]))

    def test_react_to_hello(self):

        conn = MagicMock()
        conf = MagicMock()

        node = Node(node_name='node', key='ffffffff')
        keys_auth = KeysAuth(self.path)
        keys_auth.key = node.key
        keys_auth.key_id = node.key

        peer_session = PeerSession(conn)
        peer_session.p2p_service = P2PService(node, conf, keys_auth, False)
        peer_session.p2p_service.metadata_manager = MagicMock()
        peer_session.send = MagicMock()
        peer_session.disconnect = MagicMock()
        peer_session._solve_challenge = MagicMock()

        def create_verify(value):
            def verify(*args):
                return value
            return verify

        key_id = 'deadbeef'
        peer_info = MagicMock()
        peer_info.key = key_id
        msg = MessageHello(port=1, node_name='node2', client_key_id=key_id, node_info=peer_info,
                           proto_id=-1)

        peer_session.verify = create_verify(False)
        peer_session._react_to_hello(msg)
        peer_session.disconnect.assert_called_with(PeerSession.DCRUnverified)

        peer_session.verify = create_verify(True)
        peer_session._react_to_hello(msg)
        peer_session.disconnect.assert_called_with(PeerSession.DCRProtocolVersion)

        msg.proto_id = P2P_PROTOCOL_ID

        peer_session._react_to_hello(msg)
        assert key_id in peer_session.p2p_service.peers
        assert peer_session.p2p_service.peers[key_id]

        peer_session.p2p_service.peers[key_id] = MagicMock()
        conn.opened = True
        peer_session.key_id = None

        peer_session._react_to_hello(msg)
        peer_session.disconnect.assert_called_with(PeerSession.DCRDuplicatePeers)

    def test_dropped(self):
        conn = MagicMock()
        peer_session = PeerSession(conn)
        peer_session.p2p_service = MagicMock()

        peer_session.remove_on_disconnect = True
        peer_session.dropped()
        assert peer_session.p2p_service.remove_peer.called
        assert not peer_session.p2p_service.remove_pending_conn.called


class TestPeerSessionInfo(unittest.TestCase):

    def test(self):

        session = PeerSession(MagicMock())

        session.unknown_property = False
        session_info = PeerSessionInfo(session)

        attributes = [
            'address', 'port',
            'verified', 'rand_val',
            'degree', 'key_id',
            'node_name', 'node_info',
            'listen_port', 'conn_id'
        ]

        for attr in attributes:
            assert hasattr(session_info, attr)
        assert not hasattr(session_info, 'unknown_property')
