import mock
from mock import MagicMock, Mock
import random
import unittest

from golem import testutils
from golem.core.keysauth import EllipticalKeysAuth, KeysAuth
from golem.core.variables import APP_VERSION, P2P_PROTOCOL_ID
from golem.network.p2p.node import Node
from golem.network.p2p.p2pservice import P2PService
from golem.network.p2p.peersession import (PeerSession, logger, PeerSessionInfo)
from golem.network.transport.message import \
    MessageHello, MessageStopGossip, MessageRandVal
from golem.tools.assertlogs import LogTestCase
from golem.tools.testwithappconfig import TestWithKeysAuth


class TestPeerSession(TestWithKeysAuth, LogTestCase, testutils.PEP8MixIn):
    PEP8_FILES = ['golem/network/p2p/peersession.py']

    def setUp(self):
        super(TestPeerSession, self).setUp()
        random.seed()
        self.peer_session = PeerSession(MagicMock())

    def __setup_handshake_server_test(self, send_mock):
        self.peer_session.conn.server.node = node = 'node info'
        self.peer_session.conn.server.node_name = node_name = 'node name'
        self.peer_session.conn.server.keys_auth.get_key_id.return_value = \
            key_id = 'server_key_id'
        self.peer_session.conn.server.metadata_manager.\
            get_metadata.return_value = metadata = 'metadata'
        self.peer_session.conn.server.cur_port = port = random.randint(1, 50000)
        self.peer_session.conn_type = self.peer_session.CONN_TYPE_SERVER
        self.peer_session.start()
        self.assertEqual(1, send_mock.call_count)
        expected = {
            'CHALLENGE': None,
            'CLIENT_KEY_ID': key_id,
            'CLI_VER': APP_VERSION,
            'DIFFICULTY': 0,
            'METADATA': metadata,
            'NODE_INFO': node,
            'NODE_NAME': node_name,
            'PORT': port,
            'PROTO_ID': P2P_PROTOCOL_ID,
            'RAND_VAL': self.peer_session.rand_val,
            'SOLVE_CHALLENGE': False,
        }
        self.assertEqual(send_mock.call_args[0][1].dict_repr(), expected)

        def find_peer(key):
            if key == key_id:
                return self.peer_session
            return None
        self.peer_session.p2p_service.find_peer = find_peer
        self.peer_session.p2p_service.enough_peers = lambda: False

        client_peer_info = MagicMock()
        client_peer_info.key = 'client_key_id'
        client_hello = MessageHello(port=1, node_name='client',
                                    rand_val=random.random(),
                                    client_key_id=client_peer_info.key,
                                    node_info=client_peer_info,
                                    proto_id=P2P_PROTOCOL_ID)
        return client_hello

    @mock.patch('golem.network.transport.session.BasicSession.send')
    def test_handshake_server_successful(self, send_mock):
        client_hello = self.__setup_handshake_server_test(send_mock)
        self.peer_session._react_to_hello(client_hello)
        self.peer_session._react_to_rand_val(
            MessageRandVal(rand_val=self.peer_session.rand_val))

        self.assertTrue(self.peer_session.verified)
        self.assertEqual(2, send_mock.call_count)
        self.assertEqual(
            send_mock.call_args_list[1][0][1].dict_repr(),
            {'RAND_VAL': client_hello.rand_val})

    @mock.patch('golem.network.transport.session.BasicSession.send')
    def test_handshake_server_protoid(self, send_mock):
        client_hello = self.__setup_handshake_server_test(send_mock)
        client_hello.proto_id = -1
        self.peer_session._react_to_hello(client_hello)
        self.assertEqual(2, send_mock.call_count)
        self.assertEqual(
            send_mock.call_args_list[1][0][1].dict_repr(),
            {'DISCONNECT_REASON': PeerSession.DCRProtocolVersion})

    @mock.patch('golem.network.transport.session.BasicSession.send')
    def test_handshake_server_randval(self, send_mock):
        client_hello = self.__setup_handshake_server_test(send_mock)
        self.peer_session._react_to_hello(client_hello)
        self.peer_session._react_to_rand_val(MessageRandVal(rand_val=-1))
        self.assertEqual(3, send_mock.call_count)
        self.assertEqual(
            send_mock.call_args_list[1][0][1].dict_repr(),
            {'RAND_VAL': client_hello.rand_val})
        self.assertEqual(
            send_mock.call_args_list[2][0][1].dict_repr(),
            {'DISCONNECT_REASON': PeerSession.DCRUnverified})

    def __setup_handshake_client_test(self, send_mock):
        self.peer_session.conn.server.node = node = 'node info'
        self.peer_session.conn.server.node_name = node_name = 'node name'
        self.peer_session.conn.server.keys_auth.get_key_id.return_value = \
            key_id = 'client_key_id'
        self.peer_session.conn.server.metadata_manager.\
            get_metadata.return_value = metadata = 'metadata'
        self.peer_session.conn.server.cur_port = port = random.randint(1, 50000)
        self.peer_session.conn_type = self.peer_session.CONN_TYPE_CLIENT
        self.peer_session.start()
        self.assertEqual(0, send_mock.call_count)
        server_peer_info = MagicMock()
        server_peer_info.key = 'server_key_id'

        def find_peer(key):
            if key == key_id:
                return self.peer_session
            return None
        self.peer_session.p2p_service.find_peer = find_peer
        self.peer_session.p2p_service.should_solve_challenge = False
        self.peer_session.p2p_service.enough_peers = lambda: False
        server_hello = MessageHello(port=1, node_name='server',
                                    rand_val=random.random(),
                                    client_key_id=server_peer_info.key,
                                    node_info=server_peer_info,
                                    proto_id=P2P_PROTOCOL_ID)
        expected = {
            'CHALLENGE': None,
            'CLIENT_KEY_ID': key_id,
            'CLI_VER': APP_VERSION,
            'DIFFICULTY': 0,
            'METADATA': metadata,
            'NODE_INFO': node,
            'NODE_NAME': node_name,
            'PORT': port,
            'PROTO_ID': P2P_PROTOCOL_ID,
            'RAND_VAL': self.peer_session.rand_val,
            'SOLVE_CHALLENGE': False,
        }

        return (server_hello, expected)

    @mock.patch('golem.network.transport.session.BasicSession.send')
    def test_handshake_client_successful(self, send_mock):
        server_hello, expected = self.__setup_handshake_client_test(send_mock)
        self.peer_session._react_to_hello(server_hello)
        self.assertEqual(2, send_mock.call_count)
        self.assertEqual(
            send_mock.call_args_list[0][0][1].dict_repr(),
            expected)
        self.assertEqual(
            send_mock.call_args_list[1][0][1].dict_repr(),
            {'RAND_VAL': server_hello.rand_val})
        self.assertFalse(self.peer_session.verified)
        self.peer_session._react_to_rand_val(
            MessageRandVal(rand_val=self.peer_session.rand_val))
        self.assertTrue(self.peer_session.verified)

    @mock.patch('golem.network.transport.session.BasicSession.send')
    def test_handshake_client_protoid(self, send_mock):
        server_hello, _ = self.__setup_handshake_client_test(send_mock)
        server_hello.proto_id = -1
        self.peer_session._react_to_hello(server_hello)
        self.assertEqual(1, send_mock.call_count)
        self.assertEqual(
            send_mock.call_args_list[0][0][1].dict_repr(),
            {'DISCONNECT_REASON': PeerSession.DCRProtocolVersion})
        self.assertFalse(self.peer_session.verified)

    @mock.patch('golem.network.transport.session.BasicSession.send')
    def test_handshake_client_randval(self, send_mock):
        server_hello, expected = self.__setup_handshake_client_test(send_mock)
        self.peer_session._react_to_hello(server_hello)
        self.assertEqual(2, send_mock.call_count)
        self.assertEqual(
            send_mock.call_args_list[0][0][1].dict_repr(),
            expected)
        self.assertEqual(
            send_mock.call_args_list[1][0][1].dict_repr(),
            {'RAND_VAL': server_hello.rand_val})
        self.assertFalse(self.peer_session.verified)
        self.peer_session._react_to_rand_val(MessageRandVal(rand_val=-1))
        self.assertFalse(self.peer_session.verified)

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

        data = b"abcdefghijklm" * 1000
        self.assertEqual(ps2.decrypt(ps.encrypt(data)), data)
        self.assertEqual(ps.decrypt(ps2.encrypt(data)), data)
        with self.assertLogs(logger, level='INFO') as logs:
            self.assertEqual(ps2.decrypt(data), data)
        self.assertTrue(any("not encrypted" in log for log in logs.output))

    def test_disconnect(self):
        conn = MagicMock()
        peer_session = PeerSession(conn)
        peer_session.p2p_service = MagicMock()
        peer_session.dropped = MagicMock()
        peer_session.send = MagicMock()
        peer_session.conn = Mock()

        peer_session.conn.opened = False
        peer_session.disconnect(PeerSession.DCRProtocolVersion)
        assert not peer_session.dropped.called
        assert not peer_session.send.called

        peer_session.conn.opened = True
        peer_session.disconnect(PeerSession.DCRProtocolVersion)
        assert peer_session.dropped.called
        assert peer_session.send.called

        peer_session.send.called = False
        peer_session.disconnect(PeerSession.DCRProtocolVersion)
        assert not peer_session.send.called

    def test_dropped(self):
        conn = MagicMock()
        peer_session = PeerSession(conn)
        peer_session.p2p_service = MagicMock()

        peer_session.dropped()
        assert peer_session.p2p_service.remove_peer.called
        assert not peer_session.p2p_service.remove_pending_conn.called

    def test_react_to_stop_gossip(self):
        conn = MagicMock()
        conf = MagicMock()
        conf.opt_peer_num = 10

        node = Node(node_name='node', key='ffffffff')
        keys_auth = KeysAuth(self.path)
        keys_auth.key = node.key
        keys_auth.key_id = node.key

        peer_session = PeerSession(conn)
        peer_session.p2p_service = P2PService(node, conf, keys_auth, False)
        peer_session.key_id = "NEW KEY_ID"
        peer_session._react_to_stop_gossip(MessageStopGossip())

    def test_verify(self):
        conn = MagicMock()
        peer_session = PeerSession(conn)
        keys_auth = EllipticalKeysAuth(self.path)
        peer_session.key_id = keys_auth.get_key_id()
        peer_session.p2p_service.verify_sig = keys_auth.verify
        msg = MessageStopGossip()
        assert not peer_session.verify(msg)
        msg.sig = keys_auth.sign(msg.get_short_hash())
        assert peer_session.verify(msg)

    def test_interpret(self):
        conn = MagicMock()
        peer_session = PeerSession(conn)
        peer_session.key_id = "KEY_ID"
        msg = MessageStopGossip()
        peer_session.interpret(msg)
        assert peer_session.p2p_service.set_last_message.called


class TestPeerSessionInfo(unittest.TestCase):

    def test(self):

        session = PeerSession(MagicMock())

        session.unknown_property = False
        session_info = PeerSessionInfo(session)

        simple_attributes = [
            'address', 'port',
            'verified', 'degree',
            'key_id', 'node_name',
            'listen_port', 'conn_id'
        ]
        attributes = simple_attributes + ['node_info']

        for attr in attributes:
            assert hasattr(session_info, attr)
        assert not hasattr(session_info, 'unknown_property')

        simplified = session_info.get_simplified_repr()
        for attr in simple_attributes:
            simplified[attr]
        with self.assertRaises(KeyError):
            simplified["node_id"]
