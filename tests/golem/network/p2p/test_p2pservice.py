# -*- coding: utf-8 -*-
import random
import time
import unittest.mock as mock
import uuid

from golem import testutils
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.keysauth import EllipticalKeysAuth
from golem.diag.service import DiagnosticsOutputFormat
from golem.model import MAX_STORED_HOSTS, KnownHosts
from golem.network.p2p import peersession
from golem.network.p2p.node import Node
from golem.network.p2p.p2pservice import HISTORY_LEN, P2PService
from golem.network.p2p.peersession import PeerSession
from golem.network.transport.tcpnetwork import SocketAddress
from golem.task.taskconnectionshelper import TaskConnectionsHelper


class TestP2PService(testutils.DatabaseFixture):

    def setUp(self):
        super(TestP2PService, self).setUp()
        random.seed()
        self.keys_auth = EllipticalKeysAuth(self.path)
        self.service = P2PService(
            None,
            ClientConfigDescriptor(),
            self.keys_auth,
            connect_to_known_hosts=False)

    def test_find_node(self):
        node_key_id = uuid.uuid4()

        # find_node() without parameter
        node_session = peersession.PeerSession(conn=mock.MagicMock())
        node_session.listen_port = random.randint(1, 2**16 - 1)
        node_session.address = random.randint(1, 2**32 - 1)
        node_session.node_name = 'approximately 16.8 million addresses'
        node_session.node_info = None
        self.service.peers = {
            node_key_id: peersession.PeerSessionInfo(node_session),
        }
        expected = [
            {
                'address': node_session.address,
                'port': node_session.listen_port,
                'node_name': node_session.node_name,
                'node': None,
            },
        ]
        self.assertEqual(self.service.find_node(node_key_id=None), expected)

        def randaddr() -> str:
            def dig() -> int:
                return random.randint(1, 255)

            return '{}.{}.{}.{}'.format(dig(), dig(), dig(), dig())

        # find_node() via kademlia neighbours
        neighbour_node_key_id = uuid.uuid4()
        neighbour_node = Node(
            node_name='Syndrom wstrząsu toksycznego',
            key=str(neighbour_node_key_id),
            prv_addr=randaddr(),
            prv_port=random.randint(1, 2**16 - 1))
        self.service.peer_keeper.neighbours = mock.MagicMock(
            return_value=[
                neighbour_node,
            ])
        expected = [{
            'address': neighbour_node.prv_addr,
            'port': neighbour_node.prv_port,
            'id': neighbour_node.key,
            'node': neighbour_node,
            'node_name': neighbour_node.node_name,
        }]
        self.assertEqual(self.service.find_node(node_key_id), expected)

    def test_add_to_peer_keeper(self):
        node = Node()
        node.key = EllipticalKeysAuth("TEST").get_key_id()
        m_test2 = mock.MagicMock()
        m_test3 = mock.MagicMock()
        self.service.peers["TEST3"] = m_test3
        self.service.peers["TEST2"] = m_test2
        self.service.peer_keeper = mock.MagicMock()
        node2 = Node()
        node2.key = "TEST2"
        self.service.peer_keeper.add_peer = mock.MagicMock(return_value=node2)
        self.service.add_to_peer_keeper(node)
        m_test2.ping.assert_called_with(0)
        m_test3.ping.assert_not_called()
        for i in range(100):
            self.service.peers[str(i)] = mock.MagicMock()
        node2.key = "59"
        self.service.add_to_peer_keeper(node)
        self.service.peers["59"].ping.assert_called_with(0)
        for i in list(range(58)) + list(range(60, 100)):
            self.service.peers[str(i)].ping.assert_not_called()
        node2.key = None
        self.service.add_to_peer_keeper(node)
        for i in list(range(58)) + list(range(60, 100)):
            self.service.peers[str(i)].ping.assert_not_called()
        self.service.peers["59"].ping.assert_called_once_with(0)
        m_test2.ping.assert_called_once_with(0)
        m_test3.ping.assert_not_called()
        self.assertEqual(len(self.service.peers), 102)

    def test_remove_old_peers(self):
        node = mock.MagicMock()
        node.key = EllipticalKeysAuth(self.path, "TESTPRIV").get_key_id()
        node.key_id = node.key

        self.service.last_peers_request = time.time() + 10
        self.service.add_peer(node.key, node)
        assert len(self.service.peers) == 1
        node.last_message_time = 0
        self.service.sync_network()

        assert len(self.service.peers) == 0

        self.service.add_peer(node.key, node)
        self.service.peers[node.key].last_message_time = time.time() + 1000
        assert len(self.service.peers) == 1
        self.service.sync_network()
        assert len(self.service.peers) == 1

    def test_refresh_peers(self):
        sa = SocketAddress('127.0.0.1', 11111)

        node = mock.MagicMock()
        node.key = EllipticalKeysAuth(self.path, "TESTPRIV").get_key_id()
        node.key_id = node.key
        node.address = sa

        node2 = mock.MagicMock()
        node2.key = EllipticalKeysAuth(self.path, "TESTPRIV2").get_key_id()
        node2.key_id = node2.key
        node2.address = sa

        self.service.add_peer(node.key, node)
        self.service.add_peer(node2.key, node2)

        self.service.peers[node.key].last_message_time = time.time() + 1000
        self.service.peers[node2.key].last_message_time = time.time() + 1000

        self.service.config_desc.opt_peer_num = 1000

        assert len(self.service.peers) == 2
        self.service.sync_network()
        assert len(self.service.peers) == 2

        self.service.last_refresh_peers = 0
        self.service.last_peers_request = 0
        self.service._peer_dbg_time_threshold = 0
        self.service.sync_network()
        # disabled
        assert len(self.service.peers) == 2

    def test_add_known_peer(self):
        key_id = EllipticalKeysAuth(self.path, "TESTPRIV").get_key_id()
        nominal_seeds = len(self.service.seeds)

        node = Node(
            node_name='super_node',
            key=str(key_id),
            pub_addr='1.2.3.4',
            prv_addr='1.2.3.4',
            pub_port=10000,
            prv_port=10000)
        node.prv_addresses = [node.prv_addr, '172.1.2.3']

        assert Node.is_super_node(node)

        KnownHosts.delete().execute()
        len_start = len(KnownHosts.select())

        # insert one
        self.service.add_known_peer(node, node.pub_addr, node.pub_port)
        select_1 = KnownHosts.select()
        len_1 = len(select_1)
        last_conn_1 = select_1[0].last_connected
        assert len_1 > len_start

        # advance time
        time.sleep(0.1)

        # insert duplicate
        self.service.add_known_peer(node, node.pub_addr, node.pub_port)
        select_2 = KnownHosts.select()
        len_2 = len(select_2)
        assert len_2 == len_1
        assert select_2[0].last_connected > last_conn_1

        assert len(self.service.seeds) > nominal_seeds

        # try to add more than max, we already have at least 1
        pub_prefix = '2.2.3.'
        prv_prefix = '172.1.2.'
        key_id_str = key_id
        for i in range(1, MAX_STORED_HOSTS + 6):
            i_str = str(i)
            pub = pub_prefix + i_str
            prv = prv_prefix + i_str
            n = Node(
                node_name=i_str,
                key=key_id_str + i_str,
                pub_addr=pub,
                prv_addr=prv,
                pub_port=10000,
                prv_port=10000)
            self.service.add_known_peer(n, pub, n.prv_port)

        assert len(KnownHosts.select()) == MAX_STORED_HOSTS
        assert len(self.service.seeds) == nominal_seeds

    def test_sync_free_peers(self):
        node = mock.MagicMock()
        node.key = EllipticalKeysAuth(self.path, "PRIVTEST").get_key_id()
        node.key_id = node.key
        node.pub_addr = '127.0.0.1'
        node.pub_port = 10000

        self.service.config_desc.opt_peer_num = 10
        self.service.free_peers.append(node.key)
        self.service.incoming_peers[node.key] = {
            'address': '127.0.0.1',
            'port': 10000,
            'node': node,
            'node_name': 'TEST',
            'conn_trials': 0
        }

        self.service.last_peers_request = time.time() - 60
        self.service.sync_network()

        assert not self.service.free_peers
        assert len(self.service.pending_connections) == 1

    def test_reconnect_with_seed(self):
        self.service.connect_to_seeds()
        time_ = time.time()
        last_time = self.service.last_time_tried_connect_with_seed
        self.assertLessEqual(
            self.service.last_time_tried_connect_with_seed,
            time_
        )
        self.assertLess(
            time_ - self.service.last_time_tried_connect_with_seed,
            self.service.reconnect_with_seed_threshold
        )
        self.assertEqual(len(self.service.peers), 0)
        self.service.sync_network()
        assert last_time == self.service.last_time_tried_connect_with_seed
        self.service.reconnect_with_seed_threshold = 0.1
        time.sleep(0.5)
        self.service.sync_network()
        assert last_time < self.service.last_time_tried_connect_with_seed

    @mock.patch('golem.network.p2p.p2pservice.P2PService.connect')
    def test_seeds_round_robin(self, m_connect):
        self.assertGreater(len(self.service.seeds), 0)
        self.service.connect_to_known_hosts = True
        self.service.connect_to_seeds()
        self.assertEquals(m_connect.call_count, 1)
        m_connect.reset_mock()
        m_connect.side_effect = RuntimeError('ConnectionProblem')
        self.service.connect_to_seeds()
        self.assertEquals(m_connect.call_count, len(self.service.seeds))

    def test_want_to_start_task_session(self):
        self.service.task_server = mock.MagicMock()
        self.service.task_server.task_connections_helper = \
            TaskConnectionsHelper()
        self.service.task_server.task_connections_helper.task_server = \
            self.service.task_server
        self.service.task_server.task_connections_helper \
            .is_new_conn_request = mock.Mock(side_effect=lambda *_: True)

        def true_method(*args) -> bool:
            return True

        def gen_uuid():
            return str(uuid.uuid4()).replace('-', '')

        key_id = gen_uuid()
        conn_id = gen_uuid()
        peer_id = gen_uuid()

        node_info = mock.MagicMock()
        node_info.key = key_id
        node_info.is_super_node = true_method

        peer = mock.MagicMock()
        peer.key_id = gen_uuid()

        self.service.peers[peer_id] = peer
        self.service.node = node_info

        self.service.want_to_start_task_session(key_id, node_info, conn_id)
        assert not peer.send_want_to_start_task_session.called
        self.service.want_to_start_task_session(peer.key_id, node_info,
                                                conn_id)
        assert not peer.send_want_to_start_task_session.called

        peer.key_id = peer_id
        self.service.want_to_start_task_session(peer.key_id, node_info,
                                                conn_id)
        assert peer.send_want_to_start_task_session.called

    def test_get_diagnostic(self):
        m = mock.MagicMock()
        m.transport.getPeer.return_value.port = "10432"
        m.transport.getPeer.return_value.host = "10.10.10.10"
        ps1 = PeerSession(m)
        ps1.key_id = self.keys_auth.key_id
        self.service.add_peer(self.keys_auth.key_id, ps1)
        m2 = mock.MagicMock()
        m2.transport.getPeer.return_value.port = "11432"
        m2.transport.getPeer.return_value.host = "127.0.0.1"
        ps2 = PeerSession(m2)
        keys_auth2 = EllipticalKeysAuth(self.path, "PUBTESTPATH1")
        ps2.key_id = keys_auth2.key_id
        self.service.add_peer(keys_auth2.key_id, ps2)
        self.service.get_diagnostics(DiagnosticsOutputFormat.json)

    def test(self):
        self.service.task_server = mock.Mock()
        self.service.peer_keeper = mock.Mock()
        self.service.peer_keeper.sync.return_value = dict()
        self.service.connect = mock.Mock()
        self.service.last_tasks_request = 0

        p = mock.Mock()
        p.key_id = 'deadbeef'
        p.degree = 1
        p.last_message_time = 0

        p2 = mock.Mock()
        p2.key_id = 'deadbeef02'
        p2.degree = 1
        p2.last_message_time = 0

        self.service.peers[p.key_id] = p
        self.service.peers['deadbeef02'] = p2
        self.service.peer_order = [p.key_id, p2.key_id]
        self.service.peer_keeper.sessions_to_end = [p2]

        self.service.ping_peers(1)
        assert p.ping.called

        degrees = self.service.get_peers_degree()
        assert len(degrees) == 2
        assert p.key_id in degrees

        self.service.remove_task('task_id')
        assert p.send_remove_task.called

        self.service.send_stop_gossip()
        assert p.send_stop_gossip.called

        self.service.sync_network()
        assert p.send_get_tasks.called

        self.service.remove_peer(p)
        assert p.key_id not in self.service.peers

    def test_challenge_history_len(self):
        difficulty = self.service._get_difficulty("KEY_ID")
        for i in range(3):
            challenge = self.service._get_challenge(
                self.keys_auth.get_key_id())
            self.service.solve_challenge(self.keys_auth.get_key_id(),
                                         challenge, difficulty)
        assert len(self.service.challenge_history) == 3
        assert self.service.last_challenge is not None
        for i in range(100):
            challenge = self.service._get_challenge(
                self.keys_auth.get_key_id())
            self.service.solve_challenge(self.keys_auth.get_key_id(),
                                         challenge, difficulty)

        assert len(self.service.challenge_history) == HISTORY_LEN

    def test_change_config_name(self):
        ccd = ClientConfigDescriptor()
        ccd.node_name = "test name change"
        assert self.service.node_name != "test name change"
        self.service.change_config(ccd)
        assert self.service.node_name == "test name change"

    def test_disconnect(self):
        self.service.peers = {'peer_id': mock.Mock()}
        self.service.disconnect()
        assert self.service.peers['peer_id'].dropped.called

    def test_round_robin_seeds(self):
        SEEDS_NUM = 10
        seeds = set()
        for i in range(SEEDS_NUM):
            seeds.add(('127.0.0.1', i + 1))
        self.service.seeds = seeds.copy()
        for i in range(SEEDS_NUM):
            seed = self.service._get_next_random_seed()
            seeds.remove(seed)
        assert not seeds
