# pylint: disable=protected-access,no-member

import copy
import ipaddress
import random
import sys
import unittest
import unittest.mock as mock

import semantic_version
from golem_messages import message
from pydispatch import dispatcher

import golem
from golem import clientconfigdescriptor
from golem import testutils
from golem.core.keysauth import KeysAuth
from golem.core.variables import PROTOCOL_CONST
from golem.core.variables import TASK_HEADERS_LIMIT
from golem.network.p2p.node import Node
from golem.network.p2p.p2pservice import P2PService
from golem.network.p2p.peersession import (PeerSession, PeerSessionInfo)
from golem.tools.assertlogs import LogTestCase
from tests.factories import p2p as p2p_factories


def fill_slots(msg):
    for slot in msg.__slots__:
        if hasattr(msg, slot):
            continue
        setattr(msg, slot, None)


class TestPeerSession(testutils.TempDirFixture, LogTestCase,
                      # noqa pylint: disable=too-many-public-methods
                      testutils.PEP8MixIn):
    PEP8_FILES = ['golem/network/p2p/peersession.py', ]

    def setUp(self):
        super().setUp()
        random.seed()
        self.peer_session = PeerSession(mock.MagicMock())
        node = p2p_factories.Node()
        keys_auth = KeysAuth(self.path)
        self.peer_session.conn.server = \
            self.peer_session.p2p_service = P2PService(
                node=node,
                config_desc=clientconfigdescriptor.ClientConfigDescriptor(),
                keys_auth=keys_auth,
                connect_to_known_hosts=False,
            )

    def __setup_handshake_server_test(self, send_mock) -> message.Hello:
        self.peer_session.conn.server.node = node = p2p_factories.Node()
        self.peer_session.conn.server.node_name = node_name = node.node_name
        self.peer_session.conn.server.keys_auth.key_id = \
            key_id = 'server_key_id'
        self.peer_session.conn.server.metadata_manager = mock.MagicMock()
        self.peer_session.conn.server.metadata_manager. \
            get_metadata.return_value = metadata = 'metadata'
        self.peer_session.conn.server.key_difficulty = 2
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
            node_info=node.to_dict(),
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

        client_peer_info = p2p_factories.Node()
        client_hello = message.Hello(
            port=1,
            node_name='client',
            rand_val=random.random(),
            client_key_id=client_peer_info.key,
            node_info=client_peer_info.to_dict(),
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

    @mock.patch('golem.network.transport.session.BasicSession.send')
    def test_handshake_server_key_not_difficult(self, send_mock):
        client_hello = self.__setup_handshake_server_test(send_mock)
        client_hello.node_info['key'] = 'deadbeef' * 16
        self.peer_session._react_to_hello(client_hello)

        self.assertEqual(
            send_mock.call_args_list[1][0][1].slots(),
            message.Disconnect(
                reason=message.Disconnect.REASON.KeyNotDifficult).slots())

    def __setup_handshake_client_test(self, send_mock):
        self.peer_session.conn.server.node = node = p2p_factories.Node()
        self.peer_session.conn.server.node_name = node_name = node.node_name
        self.peer_session.conn.server.keys_auth.key_id = \
            key_id = node.key
        self.peer_session.conn.server.metadata_manager = mock.MagicMock()
        self.peer_session.conn.server.metadata_manager. \
            get_metadata.return_value = metadata = 'metadata'
        self.peer_session.conn.server.cur_port = port = random.randint(1, 50000)
        self.peer_session.conn_type = self.peer_session.CONN_TYPE_CLIENT
        self.peer_session.start()
        self.assertEqual(0, send_mock.call_count)
        server_peer_info = p2p_factories.Node()

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
            node_info=server_peer_info.to_dict(),
            proto_id=PROTOCOL_CONST.ID)
        fill_slots(server_hello)
        expected = message.Hello(
            challenge=None,
            client_key_id=key_id,
            client_ver=golem.__version__,
            difficulty=None,
            metadata=metadata,
            node_info=node.to_dict(),
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
        }

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
        peer_session.p2p_service.get_own_tasks_headers = mock.Mock()
        peer_session.p2p_service.get_others_tasks_headers = mock.Mock()
        peer_session.send = mock.MagicMock()

        peer_session.p2p_service.get_own_tasks_headers.return_value = []
        peer_session.p2p_service.get_others_tasks_headers.return_value = []
        peer_session._react_to_get_tasks(mock.Mock())
        assert not peer_session.send.called

        peer_session.p2p_service.get_own_tasks_headers.return_value = list(
            range(0, 100))
        peer_session.p2p_service.get_others_tasks_headers.return_value = list()
        peer_session._react_to_get_tasks(mock.Mock())

        sent_tasks = peer_session.send.call_args_list[0][0][0].tasks
        assert len(sent_tasks) <= TASK_HEADERS_LIMIT
        assert len(sent_tasks) == len(set(sent_tasks))

        peer_session.p2p_service.get_own_tasks_headers.return_value = list(
            range(0, TASK_HEADERS_LIMIT - 1))
        peer_session.p2p_service.get_others_tasks_headers.return_value = list(
            range(0, TASK_HEADERS_LIMIT - 1))
        peer_session._react_to_get_tasks(mock.Mock())
        sent_tasks = peer_session.send.call_args_list[0][0][0].tasks
        assert len(sent_tasks) <= TASK_HEADERS_LIMIT
        assert len(sent_tasks) == len(set(sent_tasks))

    def test_react_to_get_tasks_none_list(self):
        conn = mock.MagicMock()
        peer_session = PeerSession(conn)
        peer_session.p2p_service.get_own_tasks_headers = mock.Mock()
        peer_session.p2p_service.get_others_tasks_headers = mock.Mock()
        peer_session.send = mock.MagicMock()

        peer_session.p2p_service.get_own_tasks_headers.return_value = None
        peer_session.p2p_service.get_others_tasks_headers.return_value = list(
            range(0, 10))
        peer_session._react_to_get_tasks(mock.Mock())
        sent_tasks = peer_session.send.call_args_list[0][0][0].tasks
        assert len(sent_tasks) <= TASK_HEADERS_LIMIT
        assert len(sent_tasks) == len(set(sent_tasks))

        peer_session.p2p_service.get_own_tasks_headers.return_value = list(
            range(0, 10))
        peer_session.p2p_service.get_others_tasks_headers.return_value = None
        peer_session._react_to_get_tasks(mock.Mock())
        sent_tasks = peer_session.send.call_args_list[0][0][0].tasks
        assert len(sent_tasks) <= TASK_HEADERS_LIMIT
        assert len(sent_tasks) == len(set(sent_tasks))

    def test_react_to_get_tasks_ratio(self):
        conn = mock.MagicMock()
        peer_session = PeerSession(conn)
        peer_session.p2p_service.get_own_tasks_headers = mock.Mock()
        peer_session.p2p_service.get_others_tasks_headers = mock.Mock()
        peer_session.send = mock.MagicMock()

        peer_session.p2p_service.get_own_tasks_headers.return_value = list(
            range(0, 50))
        peer_session.p2p_service.get_others_tasks_headers.return_value = list(
            range(51, 100))
        peer_session._react_to_get_tasks(mock.Mock())
        sent_tasks = peer_session.send.call_args_list[0][0][0].tasks

        my_tasks = list(filter(lambda x: x in (0, 50), sent_tasks))
        other_tasks = list(filter(lambda x: x in (50, 100), sent_tasks))

        assert len(my_tasks) <= int(TASK_HEADERS_LIMIT / 2)
        assert len(other_tasks) <= int(TASK_HEADERS_LIMIT / 2)
        assert len(sent_tasks) <= TASK_HEADERS_LIMIT
        assert len(sent_tasks) == len(set(sent_tasks))

    @mock.patch('golem.network.p2p.peersession.PeerSession._send_peers')
    def test_react_to_get_peers(self, send_mock):
        msg = message.p2p.GetPeers()
        self.peer_session._react_to_get_peers(msg)
        send_mock.assert_called_once_with()

    @mock.patch('golem.network.p2p.p2pservice.P2PService.find_node')
    @mock.patch('golem.network.p2p.peersession.PeerSession.send')
    def test_send_peers(self, send_mock, find_mock):
        node = p2p_factories.Node()
        find_mock.return_value = [
            {
                'address': node.prv_addr,
                'port': node.prv_port,
                'node_name': node.node_name,
                'node': node,
            },
        ]
        self.peer_session._send_peers()
        find_mock.assert_called_once_with(
            node_key_id=None,
            alpha=mock.ANY,
        )
        send_mock.assert_called_once_with(mock.ANY)
        msg = send_mock.call_args[0][0]
        self.assertEqual(msg.peers[0]['node'], node.to_dict())

    @mock.patch('golem.network.p2p.p2pservice.P2PService.try_to_add_peer')
    def test_react_to_peers(self, add_peer_mock):
        node = p2p_factories.Node()
        peers = [
            {
                'address': node.prv_addr,
                'port': node.prv_port,
                'node_name': node.node_name,
                'node': node.to_dict(),
            },
        ]
        msg = message.p2p.Peers(peers=copy.deepcopy(peers))
        self.peer_session._react_to_peers(msg)
        peers[0]['node'] = Node.from_dict(peers[0]['node'])
        add_peer_mock.assert_called_once_with(peers[0])


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
