import golem_messages
from golem_messages import message
import ipaddress
from pydispatch import dispatcher
import random
import semantic_version
import sys
import unittest
import unittest.mock as mock

import golem
from golem import testutils
from golem.core.keysauth import KeysAuth
from golem.core.variables import PROTOCOL_CONST
from golem.network.p2p.node import Node
from golem.network.p2p.p2pservice import P2PService
from golem.network.p2p.peersession import (PeerSession, PeerSessionInfo)
from golem.tools.assertlogs import LogTestCase
from golem.tools.testwithappconfig import TestWithKeysAuth
from golem.core.variables import TASK_HEADERS_LIMIT


def fill_slots(msg):
    for slot in msg.__slots__:
        if hasattr(msg, slot):
            continue
        setattr(msg, slot, None)


class TestPeerSession(TestWithKeysAuth, LogTestCase, testutils.PEP8MixIn):
    PEP8_FILES = ['golem/network/p2p/peersession.py', ]

    def setUp(self):
        super().setUp()
        random.seed()
        self.peer_session = PeerSession(mock.MagicMock())

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
        expected = message.Hello(
            challenge=None,
            client_key_id=key_id,
            client_ver=golem.__version__,
            difficulty=None,
            metadata=metadata,
            node_info=node,
            node_name=node_name,
            port=port,
            proto_id=PROTOCOL_CONST.ID,
            rand_val=self.peer_session.rand_val,
            solve_challenge=False,
        )

        self.assertEqual(send_mock.call_args[0][1].slots(), expected.slots())

        def find_peer(key):
            if key == key_id:
                return self.peer_session
            return None
        self.peer_session.p2p_service.find_peer = find_peer
        self.peer_session.p2p_service.enough_peers = lambda: False

        client_peer_info = mock.MagicMock()
        client_peer_info.key = 'client_key_id'
        client_hello = message.Hello(
            port=1,
            node_name='client',
            rand_val=random.random(),
            client_key_id=client_peer_info.key,
            node_info=client_peer_info,
            proto_id=PROTOCOL_CONST.ID)
        fill_slots(client_hello)
        return client_hello

    @mock.patch('golem.network.transport.session.BasicSession.send')
    def test_handshake_server_successful(self, send_mock):
        client_hello = self.__setup_handshake_server_test(send_mock)
        self.peer_session._react_to_hello(client_hello)
        self.peer_session._react_to_rand_val(
            message.RandVal(rand_val=self.peer_session.rand_val))

        self.assertTrue(self.peer_session.verified)
        self.assertEqual(2, send_mock.call_count)
        self.assertEqual(
            send_mock.call_args_list[1][0][1].slots(),
            message.RandVal(rand_val=client_hello.rand_val).slots())

    @mock.patch('golem.network.transport.session.BasicSession._react_to_hello')
    @mock.patch('golem.network.transport.session.BasicSession.send')
    def test_react_to_hello_super(self, send_mock, super_mock):
        client_hello = self.__setup_handshake_server_test(send_mock)
        self.peer_session.interpret(client_hello)
        super_mock.assert_called_once_with(client_hello)

    @mock.patch('golem.network.transport.session.BasicSession._react_to_hello')
    @mock.patch('golem.network.transport.session.BasicSession.disconnect')
    def test_react_to_hello_malformed(self, disconnect_mock, super_mock):
        """Reaction to hello without attributes"""

        malformed_hello = message.Hello()
        for attr in malformed_hello.__slots__:
            if attr in message.Message.__slots__:
                continue
            delattr(malformed_hello, attr)
        self.peer_session.interpret(malformed_hello)
        disconnect_mock.assert_called_once_with(
            message.Disconnect.REASON.ProtocolVersion,
        )

    @mock.patch('golem.network.transport.session.BasicSession.send')
    def test_handshake_server_protoid(self, send_mock):
        client_hello = self.__setup_handshake_server_test(send_mock)
        client_hello.proto_id = -1
        self.peer_session._react_to_hello(client_hello)
        self.assertEqual(2, send_mock.call_count)
        self.assertEqual(
            send_mock.call_args_list[1][0][1].slots(),
            message.Disconnect(
                reason=message.Disconnect.REASON.ProtocolVersion).slots())

    @mock.patch('golem.network.transport.session.BasicSession.send')
    def test_handshake_server_randval(self, send_mock):
        client_hello = self.__setup_handshake_server_test(send_mock)
        self.peer_session._react_to_hello(client_hello)
        self.peer_session._react_to_rand_val(
            message.RandVal(rand_val=-1))
        self.assertEqual(3, send_mock.call_count)
        self.assertEqual(
            send_mock.call_args_list[1][0][1].slots(),
            message.RandVal(rand_val=client_hello.rand_val).slots())
        self.assertEqual(
            send_mock.call_args_list[2][0][1].slots(),
            message.Disconnect(
                reason=message.Disconnect.REASON.Unverified).slots())

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
        server_peer_info = mock.MagicMock()
        server_peer_info.key = 'server_key_id'

        def find_peer(key):
            if key == key_id:
                return self.peer_session
            return None
        self.peer_session.p2p_service.find_peer = find_peer
        self.peer_session.p2p_service.should_solve_challenge = False
        self.peer_session.p2p_service.enough_peers = lambda: False
        server_hello = message.Hello(
            port=1,
            node_name='server',
            rand_val=random.random(),
            client_key_id=server_peer_info.key,
            node_info=server_peer_info,
            proto_id=PROTOCOL_CONST.ID)
        fill_slots(server_hello)
        expected = message.Hello(
            challenge=None,
            client_key_id=key_id,
            client_ver=golem.__version__,
            difficulty=None,
            metadata=metadata,
            node_info=node,
            node_name=node_name,
            port=port,
            proto_id=PROTOCOL_CONST.ID,
            rand_val=self.peer_session.rand_val,
            solve_challenge=False,
        )

        return (server_hello, expected)

    @mock.patch('golem.network.transport.session.BasicSession.send')
    def test_handshake_client_successful(self, send_mock):
        server_hello, expected = self.__setup_handshake_client_test(send_mock)
        self.peer_session._react_to_hello(server_hello)
        self.assertEqual(2, send_mock.call_count)
        self.assertEqual(
            send_mock.call_args_list[0][0][1].slots(),
            expected.slots())
        self.assertEqual(
            send_mock.call_args_list[1][0][1].slots(),
            message.RandVal(rand_val=server_hello.rand_val).slots())
        self.assertFalse(self.peer_session.verified)
        self.peer_session._react_to_rand_val(
            message.RandVal(rand_val=self.peer_session.rand_val))
        self.assertTrue(self.peer_session.verified)

    @mock.patch('golem.network.transport.session.BasicSession.send')
    def test_handshake_client_protoid(self, send_mock):
        server_hello, _ = self.__setup_handshake_client_test(send_mock)
        server_hello.proto_id = -1
        self.peer_session._react_to_hello(server_hello)
        self.assertEqual(1, send_mock.call_count)
        self.assertEqual(
            send_mock.call_args_list[0][0][1].slots(),
            message.Disconnect(
                reason=message.Disconnect.REASON.ProtocolVersion).slots())
        self.assertFalse(self.peer_session.verified)

    @mock.patch('golem.network.transport.session.BasicSession.send')
    def test_handshake_client_randval(self, send_mock):
        server_hello, expected = self.__setup_handshake_client_test(send_mock)
        self.peer_session._react_to_hello(server_hello)
        self.assertEqual(2, send_mock.call_count)
        self.assertEqual(
            send_mock.call_args_list[0][0][1].slots(),
            expected.slots())
        self.assertEqual(
            send_mock.call_args_list[1][0][1].slots(),
            message.RandVal(rand_val=server_hello.rand_val).slots())
        self.assertFalse(self.peer_session.verified)
        self.peer_session._react_to_rand_val(
            message.RandVal(rand_val=-1))
        self.assertFalse(self.peer_session.verified)

    def test_react_to_hello_new_version(self):
        listener = mock.MagicMock()
        dispatcher.connect(listener, signal='golem.p2p')
        self.peer_session.p2p_service.seeds = {
            (host, random.randint(0, 65535))
            for host in
            ipaddress.ip_network('192.0.2.0/29').hosts()
        }

        peer_info = mock.MagicMock()
        peer_info.key = (
            'What is human warfare but just this;'
            'an effort to make the laws of God and nature'
            'take sides with one party.'
        )
        msg_kwargs = {
            'port': random.randint(0, 65535),
            'node_name': 'How could youths better learn to live than by at'
                         'once trying the experiment of living? --HDT',
            'client_key_id': peer_info.key,
            'client_ver': None,
            'node_info': peer_info,
            'proto_id': random.randint(0, sys.maxsize),
            'metadata': None,
            'solve_challenge': None,
            'challenge': None,
            'difficulty': None,
            'golem_messages_version': golem_messages.__version__,
        }
        for slot in message.Hello.__slots__:
            if slot in msg_kwargs:
                continue
            msg_kwargs[slot] = None

        # Test not seed
        msg = message.Hello(**msg_kwargs)
        self.peer_session._react_to_hello(msg)
        self.assertEqual(listener.call_count, 0)
        listener.reset_mock()

        # Choose one seed
        chosen_seed = random.choice(tuple(self.peer_session.p2p_service.seeds))
        msg_kwargs['port'] = chosen_seed[1]
        self.peer_session.address = chosen_seed[0]

        # Test with seed, default version (0)
        msg = message.Hello(**msg_kwargs)
        self.peer_session._react_to_hello(msg)
        self.assertEqual(listener.call_count, 0)
        listener.reset_mock()

        # Test with seed, newer version
        version = semantic_version.Version(golem.__version__).next_patch()
        msg_kwargs['client_ver'] = str(version)
        msg = message.Hello(**msg_kwargs)
        self.peer_session._react_to_hello(msg)
        listener.assert_called_once_with(
            signal='golem.p2p',
            event='new_version',
            version=version,
            sender=mock.ANY,
        )
        listener.reset_mock()

    def test_disconnect(self):
        conn = mock.MagicMock()
        peer_session = PeerSession(conn)
        peer_session.p2p_service = mock.MagicMock()
        peer_session.dropped = mock.MagicMock()
        peer_session.send = mock.MagicMock()
        peer_session.conn = mock.Mock()

        peer_session.conn.opened = False
        peer_session.disconnect(message.Disconnect.REASON.ProtocolVersion)
        assert not peer_session.dropped.called
        assert not peer_session.send.called

        peer_session.conn.opened = True
        peer_session.disconnect(message.Disconnect.REASON.ProtocolVersion)
        assert peer_session.dropped.called
        assert peer_session.send.called

        peer_session.send.called = False
        peer_session.disconnect(message.Disconnect.REASON.ProtocolVersion)
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
        peer_session._react_to_stop_gossip(message.StopGossip())

    def test_interpret(self):
        conn = mock.MagicMock()
        peer_session = PeerSession(conn)
        peer_session.key_id = "KEY_ID"
        msg = message.StopGossip()
        peer_session.interpret(msg)
        assert peer_session.p2p_service.set_last_message.called

    def test_react_to_get_tasks(self):
        conn = mock.MagicMock()
        peer_session = PeerSession(conn)
        peer_session.p2p_service.get_tasks_headers = mock.Mock()
        peer_session.send = mock.MagicMock()

        peer_session.p2p_service.get_tasks_headers.return_value = [], []
        peer_session._react_to_get_tasks(mock.Mock())
        assert not peer_session.send.called

        peer_session.p2p_service.get_tasks_headers.return_value = list(
            range(0, 100)), list()
        peer_session._react_to_get_tasks(mock.Mock())

        sent_tasks = peer_session.send.call_args_list[0][0][0].tasks
        assert len(sent_tasks) <= TASK_HEADERS_LIMIT
        assert len(sent_tasks) == len(set(sent_tasks))

        peer_session.p2p_service.get_tasks_headers.return_value = list(
            range(0, TASK_HEADERS_LIMIT - 1)),\
            list(range(0, TASK_HEADERS_LIMIT - 1))
        peer_session._react_to_get_tasks(mock.Mock())
        sent_tasks = peer_session.send.call_args_list[0][0][0].tasks
        assert len(sent_tasks) <= TASK_HEADERS_LIMIT
        assert len(sent_tasks) == len(set(sent_tasks))

        peer_session.p2p_service.get_tasks_headers.return_value = None,\
            list(range(0, 10))
        peer_session._react_to_get_tasks(mock.Mock())
        sent_tasks = peer_session.send.call_args_list[0][0][0].tasks
        assert len(sent_tasks) <= TASK_HEADERS_LIMIT
        assert len(sent_tasks) == len(set(sent_tasks))

        peer_session.p2p_service.get_tasks_headers.return_value =\
            list(range(0, 10)), None
        peer_session._react_to_get_tasks(mock.Mock())
        sent_tasks = peer_session.send.call_args_list[0][0][0].tasks
        assert len(sent_tasks) <= TASK_HEADERS_LIMIT
        assert len(sent_tasks) == len(set(sent_tasks))

        peer_session.p2p_service.get_tasks_headers.return_value =\
            list(range(0, 50)), list(range(51, 100))
        peer_session._react_to_get_tasks(mock.Mock())
        sent_tasks = peer_session.send.call_args_list[0][0][0].tasks

        my_tasks = list(filter(lambda x: x in (0, 50), sent_tasks))
        other_tasks = list(filter(lambda x: x in (50, 100), sent_tasks))

        assert len(my_tasks) <= int(TASK_HEADERS_LIMIT / 2)
        assert len(other_tasks) <= int(TASK_HEADERS_LIMIT / 2)
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
