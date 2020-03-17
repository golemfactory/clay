# pylint: disable=protected-access,no-member

import copy
import random
import uuid
from unittest import TestCase
from unittest.mock import patch, Mock, MagicMock, ANY

from golem_messages import message
from golem_messages.factories.datastructures import p2p as dt_p2p_factory

import golem
from golem import clientconfigdescriptor
from golem import testutils
from golem.core.keysauth import KeysAuth
from golem.core.variables import PROTOCOL_CONST
from golem.core.variables import TASK_HEADERS_LIMIT
from golem.envs import EnvSupportStatus
from golem.network.p2p.p2pservice import P2PService
from golem.network.p2p.peersession import (logger, PeerSession, PeerSessionInfo)
from golem.tools.assertlogs import LogTestCase
from tests.factories import taskserver as task_server_factory


def fill_slots(msg):
    for slot in msg.__slots__:
        if hasattr(msg, slot):
            continue
        setattr(msg, slot, None)


class TestPeerSession(testutils.DatabaseFixture, LogTestCase,
                      # noqa pylint: disable=too-many-public-methods
                      testutils.PEP8MixIn):
    PEP8_FILES = ['golem/network/p2p/peersession.py', ]

    @patch('golem.envs.default.NonHypervisedDockerCPUEnvironment')
    def setUp(self, docker_env):  # pylint: disable=arguments-differ
        super().setUp()
        random.seed()
        docker_env.supported.return_value = EnvSupportStatus(True)
        self.peer_session = PeerSession(MagicMock())
        node = dt_p2p_factory.Node()
        keys_auth = KeysAuth(self.path, 'priv_key', 'password')
        self.peer_session.conn.server = \
            self.peer_session.p2p_service = P2PService(
                node=node,
                config_desc=clientconfigdescriptor.ClientConfigDescriptor(),
                keys_auth=keys_auth,
                connect_to_known_hosts=False,
            )
        client = MagicMock()
        client.datadir = self.path
        with patch(
                'golem.network.concent.handlers_library.HandlersLibrary'
                '.register_handler',):
            self.peer_session.p2p_service.task_server = \
                task_server_factory.TaskServer(client=client)

    def __setup_handshake_server_test(self, send_mock) -> message.base.Hello:
        self.peer_session.conn.server.node = node = dt_p2p_factory.Node()
        self.peer_session.conn.server.node_name = node.node_name
        self.peer_session.conn.server.keys_auth.key_id = \
            key_id = 'server_key_id'
        self.peer_session.conn.server.cur_port = port = random.randint(1, 50000)
        self.peer_session.conn_type = self.peer_session.CONN_TYPE_SERVER
        self.peer_session.start()
        self.assertEqual(1, send_mock.call_count)
        expected = message.base.Hello(
            challenge=None,
            client_ver=golem.__version__,
            difficulty=None,
            node_info=node,
            port=port,
            proto_id=PROTOCOL_CONST.ID,
            rand_val=self.peer_session.rand_val,
            solve_challenge=False,
            metadata={},
        )

        self.assertEqual(send_mock.call_args[0][1].slots(), expected.slots())

        def find_peer(key):
            if key == key_id:
                return self.peer_session
            return None

        self.peer_session.p2p_service.find_peer = find_peer
        self.peer_session.p2p_service.enough_peers = lambda: False

        client_peer_info = dt_p2p_factory.Node()
        client_hello = message.base.Hello(
            port=1,
            rand_val=random.random(),
            node_info=client_peer_info,
            proto_id=PROTOCOL_CONST.ID)
        fill_slots(client_hello)
        return client_hello

    @patch('golem.network.transport.session.BasicSession.send')
    def test_handshake_server_successful(self, send_mock):
        client_hello = self.__setup_handshake_server_test(send_mock)
        self.peer_session._react_to_hello(client_hello)
        self.peer_session._react_to_rand_val(
            message.base.RandVal(rand_val=self.peer_session.rand_val))

        self.assertTrue(self.peer_session.verified)
        self.assertEqual(2, send_mock.call_count)
        self.assertEqual(
            send_mock.call_args_list[1][0][1].slots(),
            message.base.RandVal(rand_val=client_hello.rand_val).slots())

    @patch('golem.network.transport.session.BasicSession.disconnect')
    def test_react_to_hello_malformed(self, disconnect_mock):
        """Reaction to hello without attributes"""

        malformed_hello = message.base.Hello()
        for attr in malformed_hello.__slots__:
            if attr in message.base.Message.__slots__:
                continue
            delattr(malformed_hello, attr)
        self.peer_session.interpret(malformed_hello)
        disconnect_mock.assert_called_once_with(
            message.base.Disconnect.REASON.ProtocolVersion,
        )

    @patch('golem.network.transport.session.BasicSession.send')
    def test_handshake_server_protoid(self, send_mock):
        client_hello = self.__setup_handshake_server_test(send_mock)
        client_hello.proto_id = -1
        self.peer_session._react_to_hello(client_hello)
        self.assertEqual(2, send_mock.call_count)
        self.assertEqual(
            send_mock.call_args_list[1][0][1].slots(),
            message.base.Disconnect(
                reason=message.base.Disconnect.REASON.ProtocolVersion).slots())

    @patch('golem.network.transport.session.BasicSession.send')
    def test_handshake_server_randval(self, send_mock):
        client_hello = self.__setup_handshake_server_test(send_mock)
        self.peer_session._react_to_hello(client_hello)
        self.peer_session._react_to_rand_val(
            message.base.RandVal(rand_val=-1))
        self.assertEqual(3, send_mock.call_count)
        self.assertEqual(
            send_mock.call_args_list[1][0][1].slots(),
            message.base.RandVal(rand_val=client_hello.rand_val).slots())
        self.assertEqual(
            send_mock.call_args_list[2][0][1].slots(),
            message.base.Disconnect(
                reason=message.base.Disconnect.REASON.Unverified).slots())

    def __setup_handshake_client_test(self, send_mock):
        self.peer_session.conn.server.node = node = dt_p2p_factory.Node()
        self.peer_session.conn.server.node_name = node.node_name
        self.peer_session.conn.server.keys_auth.key_id = \
            key_id = node.key
        self.peer_session.conn.server.cur_port = port = random.randint(1, 50000)
        self.peer_session.conn_type = self.peer_session.CONN_TYPE_CLIENT
        self.peer_session.start()
        self.assertEqual(0, send_mock.call_count)
        server_peer_info = dt_p2p_factory.Node()

        def find_peer(key):
            if key == key_id:
                return self.peer_session
            return None

        self.peer_session.p2p_service.find_peer = find_peer
        self.peer_session.p2p_service.should_solve_challenge = False
        self.peer_session.p2p_service.enough_peers = lambda: False
        server_hello = message.base.Hello(
            port=1,
            rand_val=random.random(),
            node_info=server_peer_info,
            proto_id=PROTOCOL_CONST.ID,
            metadata={},
        )
        fill_slots(server_hello)
        expected = message.base.Hello(
            challenge=None,
            client_ver=golem.__version__,
            difficulty=None,
            node_info=node,
            port=port,
            proto_id=PROTOCOL_CONST.ID,
            rand_val=self.peer_session.rand_val,
            solve_challenge=False,
            metadata={},
        )

        return server_hello, expected

    @patch('golem.network.transport.session.BasicSession.send')
    def test_handshake_client_successful(self, send_mock):
        server_hello, expected = self.__setup_handshake_client_test(send_mock)
        self.peer_session._react_to_hello(server_hello)
        self.assertEqual(2, send_mock.call_count)
        self.assertEqual(
            send_mock.call_args_list[0][0][1].slots(),
            expected.slots())
        self.assertEqual(
            send_mock.call_args_list[1][0][1].slots(),
            message.base.RandVal(rand_val=server_hello.rand_val).slots())
        self.assertFalse(self.peer_session.verified)
        self.peer_session._react_to_rand_val(
            message.base.RandVal(rand_val=self.peer_session.rand_val))
        self.assertTrue(self.peer_session.verified)

    @patch('golem.network.transport.session.BasicSession.send')
    def test_handshake_client_protoid(self, send_mock):
        server_hello, _ = self.__setup_handshake_client_test(send_mock)
        server_hello.proto_id = -1
        self.peer_session._react_to_hello(server_hello)
        self.assertEqual(1, send_mock.call_count)
        self.assertEqual(
            send_mock.call_args_list[0][0][1].slots(),
            message.base.Disconnect(
                reason=message.base.Disconnect.REASON.ProtocolVersion).slots())
        self.assertFalse(self.peer_session.verified)

    @patch('golem.network.transport.session.BasicSession.send')
    def test_handshake_client_randval(self, send_mock):
        server_hello, expected = self.__setup_handshake_client_test(send_mock)
        self.peer_session._react_to_hello(server_hello)
        self.assertEqual(2, send_mock.call_count)
        self.assertEqual(
            send_mock.call_args_list[0][0][1].slots(),
            expected.slots())
        self.assertEqual(
            send_mock.call_args_list[1][0][1].slots(),
            message.base.RandVal(rand_val=server_hello.rand_val).slots())
        self.assertFalse(self.peer_session.verified)
        self.peer_session._react_to_rand_val(
            message.base.RandVal(rand_val=-1))
        self.assertFalse(self.peer_session.verified)

    def test_disconnect(self):
        conn = MagicMock()
        peer_session = PeerSession(conn)
        peer_session.p2p_service = MagicMock()
        peer_session.dropped = MagicMock()
        peer_session.send = MagicMock()
        peer_session.conn = Mock()

        peer_session.conn.opened = False
        peer_session.disconnect(message.base.Disconnect.REASON.ProtocolVersion)
        assert not peer_session.dropped.called
        assert not peer_session.send.called

        peer_session.conn.opened = True
        peer_session.disconnect(message.base.Disconnect.REASON.ProtocolVersion)
        assert peer_session.dropped.called
        assert peer_session.send.called

        peer_session.send.called = False
        peer_session.disconnect(message.base.Disconnect.REASON.ProtocolVersion)
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

        node = dt_p2p_factory.Node(node_name='node', key='ffffffff')
        keys_auth = KeysAuth(self.path, 'priv_key', 'password')

        peer_session = PeerSession(conn)
        peer_session.p2p_service = P2PService(node, conf, keys_auth, False)
        peer_session.key_id = "NEW KEY_ID"
        peer_session._react_to_stop_gossip(message.p2p.StopGossip())

    def test_interpret(self):
        conn = MagicMock()
        peer_session = PeerSession(conn)
        peer_session.key_id = "KEY_ID"
        msg = message.p2p.StopGossip()
        peer_session.interpret(msg)
        assert peer_session.p2p_service.set_last_message.called

    def test_react_to_get_tasks(self):
        conn = MagicMock()
        peer_session = PeerSession(conn)
        peer_session.p2p_service.get_own_tasks_headers = Mock()
        peer_session.p2p_service.get_others_tasks_headers = Mock()
        peer_session.send = MagicMock()

        peer_session.p2p_service.get_own_tasks_headers.return_value = []
        peer_session.p2p_service.get_others_tasks_headers.return_value = []
        peer_session._react_to_get_tasks(Mock())
        assert not peer_session.send.called

        peer_session.p2p_service.get_own_tasks_headers.return_value = list(
            range(0, 100))
        peer_session.p2p_service.get_others_tasks_headers.return_value = list()
        peer_session._react_to_get_tasks(Mock())

        sent_tasks = peer_session.send.call_args_list[0][0][0].tasks
        assert len(sent_tasks) <= TASK_HEADERS_LIMIT
        assert len(sent_tasks) == len(set(sent_tasks))

        peer_session.p2p_service.get_own_tasks_headers.return_value = list(
            range(0, TASK_HEADERS_LIMIT - 1))
        peer_session.p2p_service.get_others_tasks_headers.return_value = list(
            range(0, TASK_HEADERS_LIMIT - 1))
        peer_session._react_to_get_tasks(Mock())
        sent_tasks = peer_session.send.call_args_list[0][0][0].tasks
        assert len(sent_tasks) <= TASK_HEADERS_LIMIT
        assert len(sent_tasks) == len(set(sent_tasks))

    def test_react_to_get_tasks_none_list(self):
        conn = MagicMock()
        peer_session = PeerSession(conn)
        peer_session.p2p_service.get_own_tasks_headers = Mock()
        peer_session.p2p_service.get_others_tasks_headers = Mock()
        peer_session.send = MagicMock()

        peer_session.p2p_service.get_own_tasks_headers.return_value = None
        peer_session.p2p_service.get_others_tasks_headers.return_value = list(
            range(0, 10))
        peer_session._react_to_get_tasks(Mock())
        sent_tasks = peer_session.send.call_args_list[0][0][0].tasks
        assert len(sent_tasks) <= TASK_HEADERS_LIMIT
        assert len(sent_tasks) == len(set(sent_tasks))

        peer_session.p2p_service.get_own_tasks_headers.return_value = list(
            range(0, 10))
        peer_session.p2p_service.get_others_tasks_headers.return_value = None
        peer_session._react_to_get_tasks(Mock())
        sent_tasks = peer_session.send.call_args_list[0][0][0].tasks
        assert len(sent_tasks) <= TASK_HEADERS_LIMIT
        assert len(sent_tasks) == len(set(sent_tasks))

    def test_react_to_get_tasks_ratio(self):
        conn = MagicMock()
        peer_session = PeerSession(conn)
        peer_session.p2p_service.get_own_tasks_headers = Mock()
        peer_session.p2p_service.get_others_tasks_headers = Mock()
        peer_session.send = MagicMock()

        peer_session.p2p_service.get_own_tasks_headers.return_value = list(
            range(0, 50))
        peer_session.p2p_service.get_others_tasks_headers.return_value = list(
            range(51, 100))
        peer_session._react_to_get_tasks(Mock())
        sent_tasks = peer_session.send.call_args_list[0][0][0].tasks

        my_tasks = list(filter(lambda x: x in (0, 50), sent_tasks))
        other_tasks = list(filter(lambda x: x in (50, 100), sent_tasks))

        assert len(my_tasks) <= int(TASK_HEADERS_LIMIT / 2)
        assert len(other_tasks) <= int(TASK_HEADERS_LIMIT / 2)
        assert len(sent_tasks) <= TASK_HEADERS_LIMIT
        assert len(sent_tasks) == len(set(sent_tasks))

    @patch('golem.network.p2p.peersession.PeerSession._send_peers')
    def test_react_to_get_peers(self, send_mock):
        msg = message.p2p.GetPeers()
        self.peer_session._react_to_get_peers(msg)
        send_mock.assert_called_once_with()

    @patch('golem.network.p2p.p2pservice.P2PService.find_node')
    @patch('golem.network.p2p.peersession.PeerSession.send')
    def test_send_peers(self, send_mock, find_mock):
        node = dt_p2p_factory.Node()
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
            alpha=ANY,
        )
        send_mock.assert_called_once_with(ANY)
        msg = send_mock.call_args[0][0]
        self.assertEqual(msg.peers[0]['node'], node)

    @patch('golem.network.p2p.p2pservice.P2PService.try_to_add_peer')
    def test_react_to_peers(self, add_peer_mock):
        peers = [dt_p2p_factory.Peer(), ]
        msg = message.p2p.Peers(peers=copy.deepcopy(peers))
        self.peer_session._react_to_peers(msg)
        add_peer_mock.assert_called_once_with(peers[0])

    @patch('golem.network.p2p.peersession.PeerSession.send')
    def test_send_remove_task(self, send_mock):
        self.peer_session.send_remove_task("some random string")
        send_mock.assert_called()
        assert isinstance(send_mock.call_args[0][0], message.p2p.RemoveTask)

    @patch('golem.envs.default.NonHypervisedDockerCPUEnvironment')
    def _gen_data_for_test_react_to_remove_task(self, docker_env):
        docker_env.supported.return_value = EnvSupportStatus(True)
        keys_auth = KeysAuth(self.path, 'priv_key', 'password')
        previous_ka = self.peer_session.p2p_service.keys_auth
        self.peer_session.p2p_service.keys_auth = keys_auth

        # Unknown task owner
        client = MagicMock()
        client.datadir = self.path
        with patch('golem.network.concent.handlers_library.HandlersLibrary'
                   '.register_handler',):
            task_server = task_server_factory.TaskServer(client=client,)
        self.peer_session.p2p_service.task_server = task_server
        peer_mock = MagicMock()
        self.peer_session.p2p_service.peers["ABC"] = peer_mock

        task_id = "test_{}".format(uuid.uuid4())
        msg = message.p2p.RemoveTask(task_id=task_id)
        msg.serialize(sign_as=keys_auth._private_key)
        assert keys_auth.verify(msg.sig, msg.get_short_hash(), keys_auth.key_id)
        return msg, task_id, previous_ka

    def test_react_to_remove_task_unknown_task_owner(self):
        msg, task_id, previous_ka = \
            self._gen_data_for_test_react_to_remove_task()
        with self.assertNoLogs(logger, level="INFO"):
            self.peer_session._react_to_remove_task(msg)
        self.peer_session.p2p_service.keys_auth = previous_ka

    def test_react_to_remove_task_wrong_task_owner(self):
        msg, task_id, previous_ka = \
            self._gen_data_for_test_react_to_remove_task()
        th_mock = MagicMock()
        th_mock.task_owner.key = "UNKNOWNKEY"
        task_server = self.peer_session.p2p_service.task_server
        task_server.task_keeper.task_headers[task_id] = th_mock
        with self.assertLogs(logger, level="INFO") as log:
            self.peer_session._react_to_remove_task(msg)
        assert "Someone tries to remove task header: " in log.output[0]
        assert task_id in log.output[0]
        assert task_server.task_keeper.task_headers[task_id] == th_mock
        self.peer_session.p2p_service.keys_auth = previous_ka

    def test_react_to_remove_task_broadcast(self):
        msg, task_id, previous_ka = \
            self._gen_data_for_test_react_to_remove_task()
        th_mock = MagicMock()
        keys_auth = self.peer_session.p2p_service.keys_auth
        th_mock.task_owner.key = keys_auth.key_id
        task_server = self.peer_session.p2p_service.task_server
        task_server.task_keeper.task_headers[task_id] = th_mock
        msg.serialize()
        with self.assertNoLogs(logger, level="INFO"):
            self.peer_session._react_to_remove_task(msg)
        assert task_server.task_keeper.task_headers.get(task_id) is None
        peer_mock = self.peer_session.p2p_service.peers["ABC"]
        arg = peer_mock.send.call_args[0][0]
        assert isinstance(arg, message.p2p.RemoveTaskContainer)
        assert arg.remove_tasks == [msg]
        self.peer_session.p2p_service.keys_auth = previous_ka

    def test_react_to_remove_task_no_broadcast(self):
        msg, task_id, previous_ka = \
            self._gen_data_for_test_react_to_remove_task()
        with self.assertNoLogs(logger, level="INFO"):
            self.peer_session._react_to_remove_task(msg)
        peer_mock = self.peer_session.p2p_service.peers["ABC"]
        peer_mock.send.assert_not_called()
        self.peer_session.p2p_service.keys_auth = previous_ka

    @patch('golem.network.p2p.peersession.PeerSession.send')
    def test_send_want_start_task_session(self, mock_send):
        node = dt_p2p_factory.Node()
        super_node = dt_p2p_factory.Node()
        self.peer_session.send_want_to_start_task_session(node, "CONN_ID",
                                                          super_node)
        msg = mock_send.call_args[0][0]
        assert isinstance(msg, message.p2p.WantToStartTaskSession)
        self.peer_session._react_to_want_to_start_task_session(msg)

    @patch('golem.network.p2p.peersession.PeerSession.send')
    def test_send_want_start_task_session_with_supernode_none(self, mock_send):
        node = dt_p2p_factory.Node()
        self.peer_session.send_want_to_start_task_session(node, "CONN_ID", None)

        msg = mock_send.call_args[0][0]
        assert isinstance(msg, message.p2p.WantToStartTaskSession)
        assert msg.super_node_info is None

        self.peer_session._react_to_want_to_start_task_session(msg)

    @patch('golem.network.p2p.peersession.PeerSession.send')
    def test_set_task_session(self, mock_send):
        node = dt_p2p_factory.Node()
        super_node = dt_p2p_factory.Node()
        self.peer_session.send_set_task_session("KEY_ID", node, "CONN_ID",
                                                super_node)
        msg = mock_send.call_args[0][0]
        assert isinstance(msg, message.p2p.SetTaskSession)
        assert msg.key_id == "KEY_ID"

        self.peer_session._react_to_set_task_session(msg)

    @patch('golem.network.p2p.peersession.PeerSession.send')
    def test_set_task_session_with_supernode_none(self, mock_send):
        node = dt_p2p_factory.Node()
        self.peer_session.send_set_task_session("KEY_ID", node, "CONN_ID", None)
        msg = mock_send.call_args[0][0]
        assert isinstance(msg, message.p2p.SetTaskSession)
        assert msg.super_node_info is None
        assert msg.key_id == "KEY_ID"

        self.peer_session._react_to_set_task_session(msg)


class TestPeerSessionInfo(TestCase):

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
