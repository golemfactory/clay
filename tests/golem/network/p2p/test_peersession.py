from golem_messages import message
import random
import unittest
import unittest.mock as mock

from golem import testutils
from golem.core.keysauth import EllipticalKeysAuth, KeysAuth
from golem.core.variables import APP_VERSION, PROTOCOL_CONST
from golem.network.p2p.node import Node
from golem.network.p2p.p2pservice import P2PService
from golem.network.p2p.peersession import (PeerSession, logger, PeerSessionInfo)
from golem.tools.assertlogs import LogTestCase
from golem.tools.testwithappconfig import TestWithKeysAuth
from golem.core.variables import TASK_HEADERS_LIMIT


class TestPeerSession(TestWithKeysAuth, LogTestCase, testutils.PEP8MixIn):
    PEP8_FILES = ['golem/network/p2p/peersession.py',]

    def setUp(self):
        super(TestPeerSession, self).setUp()
        random.seed()
        self.peer_session = PeerSession(mock.MagicMock())

    @mock.patch('golem.network.transport.session.BasicSession.send')
    def test_hello(self, send_mock):
        self.maxDiff = None
        self.peer_session.conn.server.node = node = 'node info'
        self.peer_session.conn.server.node_name = node_name = 'node name'
        self.peer_session.conn.server.keys_auth.get_key_id.return_value = \
            key_id = 'client_key_id'
        self.peer_session.conn.server.metadata_manager.\
            get_metadata.return_value = metadata = 'metadata'
        self.peer_session.conn.server.cur_port = port = random.randint(1, 50000)
        self.peer_session.hello()
        send_mock.assert_called_once_with(mock.ANY, mock.ANY)

        expected = [
            ['rand_val', self.peer_session.rand_val],
            ['proto_id', PROTOCOL_CONST.P2P_ID],
            ['node_name', node_name],
            ['node_info', node],
            ['port', port],
            ['client_ver', APP_VERSION],
            ['client_key_id', key_id],
            ['solve_challenge', False],
            ['challenge', None],
            ['difficulty', 0],
            ['metadata', metadata],
        ]

        self.assertEqual(send_mock.call_args[0][1].slots(), expected)

    def test_encrypt_decrypt(self):
        ps = PeerSession(mock.MagicMock())
        ps2 = PeerSession(mock.MagicMock())

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
        with self.assertLogs(logger, level='INFO') as l:
            self.assertEqual(ps2.decrypt(data), data)
        self.assertTrue(any("not encrypted" in log for log in l.output))

    def test_react_to_hello(self):

        conn = mock.MagicMock()
        conf = mock.MagicMock()
        conf.opt_peer_num = 10

        node = Node(node_name='node', key='ffffffff')
        keys_auth = KeysAuth(self.path)
        keys_auth.key = node.key
        keys_auth.key_id = node.key

        peer_session = PeerSession(conn)
        peer_session.p2p_service = P2PService(node, conf, keys_auth, False)
        peer_session.p2p_service.metadata_manager = mock.MagicMock()
        peer_session.send = mock.MagicMock()
        peer_session.disconnect = mock.MagicMock()
        peer_session._solve_challenge = mock.MagicMock()

        def create_verify(value):
            def verify(*args):
                return value
            return verify

        key_id = 'deadbeef'
        peer_info = mock.MagicMock()
        peer_info.key = key_id
        msg = message.MessageHello(port=1, node_name='node2', client_key_id=key_id,
                           node_info=peer_info, proto_id=-1)

        peer_session.verify = create_verify(False)
        peer_session._react_to_hello(msg)
        peer_session.disconnect.assert_called_with(PeerSession.DCRUnverified)

        peer_session.verify = create_verify(True)
        peer_session._react_to_hello(msg)
        peer_session.disconnect.assert_called_with(
            PeerSession.DCRProtocolVersion)

        msg.proto_id = PROTOCOL_CONST.P2P_ID

        peer_session._react_to_hello(msg)
        assert key_id in peer_session.p2p_service.peers
        assert peer_session.p2p_service.peers[key_id]

        peer_session.p2p_service.peers[key_id] = mock.MagicMock()
        conn.opened = True
        peer_session.key_id = None

        peer_session._react_to_hello(msg)
        peer_session.disconnect.assert_called_with(
            PeerSession.DCRDuplicatePeers)

    def test_disconnect(self):
        conn = mock.MagicMock()
        peer_session = PeerSession(conn)
        peer_session.p2p_service = mock.MagicMock()
        peer_session.dropped = mock.MagicMock()
        peer_session.send = mock.MagicMock()
        peer_session.conn = mock.Mock()

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
        conn = mock.MagicMock()
        peer_session = PeerSession(conn)
        peer_session.p2p_service = mock.MagicMock()

        peer_session.dropped()
        assert peer_session.p2p_service.remove_peer.called
        assert not peer_session.p2p_service.remove_pending_conn.called

    def test_react_to_stop_gossip(self):
        conn = mock.MagicMock()
        conf = mock.MagicMock()
        conf.opt_peer_num = 10

        node = Node(node_name='node', key='ffffffff')
        keys_auth = KeysAuth(self.path)
        keys_auth.key = node.key
        keys_auth.key_id = node.key

        peer_session = PeerSession(conn)
        peer_session.p2p_service = P2PService(node, conf, keys_auth, False)
        peer_session.key_id = "NEW KEY_ID"
        peer_session._react_to_stop_gossip(message.MessageStopGossip())

    def test_verify(self):
        conn = mock.MagicMock()
        peer_session = PeerSession(conn)
        keys_auth = EllipticalKeysAuth(self.path)
        peer_session.key_id = keys_auth.get_key_id()
        peer_session.p2p_service.verify_sig = keys_auth.verify
        msg = message.MessageStopGossip()
        assert not peer_session.verify(msg)
        msg.sig = keys_auth.sign(msg.get_short_hash())
        assert peer_session.verify(msg)

    def test_interpret(self):
        conn = mock.MagicMock()
        peer_session = PeerSession(conn)
        peer_session.key_id = "KEY_ID"
        msg = message.MessageStopGossip()
        peer_session.interpret(msg)
        assert peer_session.p2p_service.set_last_message.called

    def test_react_to_get_tasks(self):
        conn = mock.MagicMock()
        peer_session = PeerSession(conn)
        peer_session.p2p_service.get_tasks_headers = mock.Mock()
        peer_session.send = mock.MagicMock()

        peer_session.p2p_service.get_tasks_headers.return_value = []
        peer_session._react_to_get_tasks(mock.Mock())
        assert not peer_session.send.called

        peer_session.p2p_service.get_tasks_headers.return_value = list(
            range(0, 100))
        peer_session._react_to_get_tasks(mock.Mock())

        sent_tasks = peer_session.send.call_args_list[0][0][0].tasks
        assert len(sent_tasks) <= TASK_HEADERS_LIMIT
        assert len(sent_tasks) == len(set(sent_tasks))

        peer_session.p2p_service.get_tasks_headers.return_value = list(
            range(0, TASK_HEADERS_LIMIT-1))
        peer_session._react_to_get_tasks(mock.Mock())
        sent_tasks = peer_session.send.call_args_list[0][0][0].tasks
        assert len(sent_tasks) <= TASK_HEADERS_LIMIT
        assert len(sent_tasks) == len(set(sent_tasks))

class TestPeerSessionInfo(unittest.TestCase):

    def test(self):

        session = PeerSession(mock.MagicMock())

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
