import os
import random
import uuid
from collections import deque
from math import ceil
from unittest.mock import Mock, MagicMock, patch

from golem_messages.message import ComputeTaskDef
from requests import HTTPError

import golem
from golem import model
from golem import testutils
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.common import timeout_to_deadline
from golem.core.idgenerator import generate_id, generate_new_id_from_id
from golem.core.keysauth import KeysAuth
from golem.environments.environment import SupportStatus, UnsupportReason
from golem.network.hyperdrive.client import HyperdriveClientOptions, \
    HyperdriveClient, to_hyperg_peer
from golem.network.p2p.node import Node
from golem.resource.dirmanager import DirManager
from golem.resource.hyperdrive.resource import ResourceError
from golem.resource.hyperdrive.resourcesmanager import HyperdriveResourceManager
from golem.task import tasksession
from golem.task.taskbase import TaskHeader, ResultType
from golem.task.taskserver import TASK_CONN_TYPES
from golem.task.taskserver import TaskServer, WaitingTaskResult, logger
from golem.task.tasksession import TaskSession
from golem.task.taskstate import TaskState
from golem.tools.assertlogs import LogTestCase
from golem.tools.testwithreactor import TestDatabaseWithReactor
from golem.utils import encode_hex


def get_example_task_header(key_id):
    return {
        "task_id": generate_id(key_id),
        "node_name": "ABC",
        "environment": "DEFAULT",
        "task_owner": dict(
            prv_port=40103,
            prv_addr='10.0.0.10'
        ),
        "task_owner_port": 10101,
        "task_owner_key_id": encode_hex(key_id),
        "task_owner_address": "10.10.10.10",
        "deadline": timeout_to_deadline(1201),
        "subtask_timeout": 120,
        "max_price": 20,
        "resource_size": 2 * 1024,
        "estimated_memory": 3 * 1024,
        "signature": None,
        "min_version": golem.__version__,
    }


def get_mock_task(key_gen, subtask_id):
    task_mock = Mock()
    key_id = str.encode(key_gen)
    task_mock.header = TaskHeader.from_dict(get_example_task_header(key_id))
    task_id = task_mock.header.task_id
    task_mock.header.max_price = 1010
    task_mock.query_extra_data.return_value.ctd = ComputeTaskDef(
        task_id=task_id,
        subtask_id=subtask_id,
    )
    return task_mock


class TestTaskServer(LogTestCase, testutils.DatabaseFixture,  # noqa pylint: disable=too-many-public-methods
                     testutils.TestWithClient):

    def setUp(self):
        for parent in self.__class__.__bases__:
            parent.setUp(self)
        random.seed()
        self.ccd = ClientConfigDescriptor()
        with patch(
                'golem.network.concent.handlers_library.HandlersLibrary'
                '.register_handler',):
            self.ts = TaskServer(
                node=Node(),
                config_desc=self.ccd,
                client=self.client,
                use_docker_manager=False,
            )

    def tearDown(self):
        LogTestCase.tearDown(self)
        testutils.DatabaseFixture.tearDown(self)

        if hasattr(self, "ts") and self.ts:
            self.ts.quit()

    @patch(
        'golem.network.concent.handlers_library.HandlersLibrary'
        '.register_handler',
    )
    @patch('golem.task.taskarchiver.TaskArchiver')
    def test_request(self, tar, *_):
        ccd = ClientConfigDescriptor()
        ccd.min_price = 10
        n = Node()
        ts = TaskServer(
            node=n,
            config_desc=ccd,
            client=self.client,
            use_docker_manager=False,
            task_archiver=tar,
        )
        ts.verify_header_sig = lambda x: True
        self.ts = ts
        ts._is_address_accessible = Mock(return_value=True)
        ts.client.get_suggested_addr.return_value = "10.10.10.10"
        ts.client.get_suggested_conn_reverse.return_value = False
        ts.client.get_requesting_trust.return_value = 0.3
        self.assertIsInstance(ts, TaskServer)
        self.assertIsNone(ts.request_task())
        n2 = Node()
        n2.prv_addr = "10.10.10.10"
        n2.port = 10101
        keys_auth = KeysAuth(self.path, 'prv_key', '')
        task_header = get_example_task_header(keys_auth.public_key)
        task_header["task_owner"] = n2
        task_id = task_header["task_id"]
        ts.add_task_header(task_header)
        self.assertEqual(ts.request_task(), task_id)
        assert ts.remove_task_header(task_id)

        task_header = get_example_task_header(keys_auth.public_key)
        task_header["task_owner_port"] = 0
        task_id2 = task_header["task_id"]
        self.assertTrue(ts.add_task_header(task_header))
        self.assertIsNotNone(ts.task_keeper.task_headers[task_id2])
        # FIXME FIx this test
        # self.assertIsNone(ts.request_task())
        # self.assertIsNone(ts.task_keeper.task_headers.get(task_id2))
        # assert not ts.remove_task_header(task_id2)
        # FIXME remove me
        ts.remove_task_header(task_id2)

        # Task can be rejected for 3 reasons at this stage; in all cases
        # the task should be reported TaskArchiver listed as unsupported:
        # 1. Requestor's trust level is too low
        tar.reset_mock()
        ts.config_desc.requesting_trust = 0.5
        task_header = get_example_task_header(keys_auth.public_key)
        task_id3 = task_header["task_id"]
        task_header["task_owner"] = n2
        ts.add_task_header(task_header)
        self.assertIsNone(ts.request_task())
        tar.add_support_status.assert_called_with(
            task_id3,
            SupportStatus(
                False,
                {UnsupportReason.REQUESTOR_TRUST: 0.3}))
        assert ts.remove_task_header(task_id3)

        # 2. Task's max price is too low
        tar.reset_mock()
        ts.config_desc.requesting_trust = 0.0
        task_header = get_example_task_header(keys_auth.public_key)
        task_id4 = task_header["task_id"]
        task_header["max_price"] = 1
        task_header["task_owner"] = n2
        ts.add_task_header(task_header)
        self.assertIsNone(ts.request_task())
        tar.add_support_status.assert_called_with(
            task_id4,
            SupportStatus(
                False,
                {UnsupportReason.MAX_PRICE: 1}))
        assert ts.remove_task_header(task_id4)

        # 3. Requestor is on a black list.
        tar.reset_mock()
        ts.acl.disallow(keys_auth.key_id)
        task_header = get_example_task_header(keys_auth.public_key)
        task_id5 = task_header["task_id"]
        task_header["task_owner"] = n2
        ts.add_task_header(task_header)
        self.assertIsNone(ts.request_task())
        tar.add_support_status.assert_called_with(
            task_id5,
            SupportStatus(
                False,
                {UnsupportReason.DENY_LIST: keys_auth.key_id}))
        assert ts.remove_task_header(task_id5)

    @patch("golem.task.taskserver.Trust")
    def test_send_results(self, trust, *_):
        ccd = ClientConfigDescriptor()
        ccd.min_price = 11
        keys_auth = KeysAuth(self.path, 'priv_key', '')
        task_header = get_example_task_header(keys_auth.public_key)
        n = Node.from_dict(task_header['task_owner'])
        ts = self.ts
        ts._is_address_accessible = Mock(return_value=True)
        ts.verify_header_sig = lambda x: True
        ts.client.get_suggested_addr.return_value = "10.10.10.10"
        ts.client.get_requesting_trust.return_value = ts.max_trust
        results = {"data": "", "result_type": ResultType.DATA}
        task_header = get_example_task_header(keys_auth.public_key)
        task_id = task_header["task_id"]
        assert ts.add_task_header(task_header)
        assert ts.request_task()
        subtask_id = generate_new_id_from_id(task_id)
        subtask_id2 = generate_new_id_from_id(task_id)
        self.assertTrue(ts.send_results(subtask_id, task_id, results, 40))
        ts.client.transaction_system.incomes_keeper.expect.reset_mock()
        self.assertTrue(ts.send_results(subtask_id2, task_id, results, 40))
        wtr = ts.results_to_send[subtask_id]
        self.assertIsInstance(wtr, WaitingTaskResult)
        self.assertEqual(wtr.subtask_id, subtask_id)
        self.assertEqual(wtr.result, "")
        self.assertEqual(wtr.result_type, ResultType.DATA)
        self.assertEqual(wtr.computing_time, 40)
        self.assertEqual(wtr.last_sending_trial, 0)
        self.assertEqual(wtr.delay_time, 0)
        self.assertEqual(wtr.owner_address, "10.10.10.10")
        self.assertEqual(wtr.owner_port, 10101)
        self.assertEqual(wtr.owner_key_id, keys_auth.key_id)
        self.assertEqual(wtr.owner, n)
        self.assertEqual(wtr.already_sending, False)
        incomes_keeper = ts.client.transaction_system.incomes_keeper
        incomes_keeper.expect.assert_called_once_with(
            sender_node_id=keys_auth.key_id,
            subtask_id=subtask_id2,
            value=1,
        )

        subtask_id3 = generate_new_id_from_id(task_id)
        with self.assertLogs(logger, level='WARNING'):
            ts.subtask_rejected(subtask_id3)
        self.assertIsNotNone(ts.task_keeper.task_headers.get(task_id))

        prev_call_count = trust.PAYMENT.increase.call_count
        ts.client.transaction_system.incomes_keeper.received.assert_not_called()
        self.assertEqual(trust.PAYMENT.increase.call_count, prev_call_count)

        ctd = ComputeTaskDef()
        ctd['task_id'] = task_id
        ctd['subtask_id'] = subtask_id
        ts.task_manager.comp_task_keeper.receive_subtask(ctd)
        model.Income.create(
            sender_node=keys_auth.public_key,
            task=ctd['task_id'],
            subtask=ctd['subtask_id'],
            value=1
        )

        from golem.model import Income
        ts.client.transaction_system. \
            incomes_keeper.received. \
            return_value = Income()

        prev_call_count = trust.PAYMENT.increase.call_count
        ts.increase_trust_payment("xyz")
        self.assertGreater(trust.PAYMENT.increase.call_count, prev_call_count)
        prev_call_count = trust.PAYMENT.decrease.call_count
        ts.decrease_trust_payment("xyz")
        self.assertGreater(trust.PAYMENT.decrease.call_count, prev_call_count)

    def test_connection_for_task_request_established(self, *_):
        ccd = ClientConfigDescriptor()
        ccd.min_price = 11
        ts = self.ts
        session = Mock()
        session.address = "10.10.10.10"
        session.port = 1020
        ts.conn_established_for_type[TASK_CONN_TYPES['task_request']](
            session, "abc", "nodename", "key", "xyz", 1010, 30, 3, 1, 2)
        self.assertEqual(session.task_id, "xyz")
        self.assertEqual(session.key_id, "key")
        self.assertEqual(session.conn_id, "abc")
        self.assertEqual(ts.task_sessions["xyz"], session)
        session.send_hello.assert_called_with()
        session.request_task.assert_called_with("nodename", "xyz", 1010, 30, 3,
                                                1, 2)

    def test_change_config(self, *_):
        ts = self.ts

        ccd2 = ClientConfigDescriptor()
        ccd2.task_session_timeout = 124
        ccd2.min_price = 0.0057
        ccd2.use_distributed_resource_management = 0
        ccd2.task_request_interval = 31
        # ccd2.use_waiting_ttl = False
        ts.change_config(ccd2)
        self.assertEqual(ts.config_desc, ccd2)
        self.assertEqual(ts.last_message_time_threshold, 124)
        self.assertEqual(ts.task_keeper.min_price, 0.0057)
        self.assertEqual(ts.task_manager.use_distributed_resources, False)
        self.assertEqual(ts.task_computer.task_request_frequency, 31)
        # self.assertEqual(ts.task_computer.use_waiting_ttl, False)

    def test_add_task_header(self, *_):
        keys_auth_2 = KeysAuth(
            os.path.join(self.path, "2"),
            'priv_key',
            'password',
        )

        ts = self.ts

        task_header = get_example_task_header(keys_auth_2.public_key)

        with self.assertRaises(Exception) as raised:
            ts.add_task_header(task_header)
            self.assertEqual(raised.exception.message, "Invalid signature")
            self.assertEqual(len(ts.get_others_tasks_headers()), 0)

        task_header["signature"] = keys_auth_2.sign(
            TaskHeader.dict_to_binary(task_header))

        self.assertIsNotNone(ts.add_task_header(task_header))
        self.assertEqual(len(ts.get_others_tasks_headers()), 1)

        task_header = get_example_task_header(keys_auth_2.public_key)
        task_id2 = task_header["task_id"]
        task_header["signature"] = keys_auth_2.sign(
            TaskHeader.dict_to_binary(task_header))

        self.assertIsNotNone(ts.add_task_header(task_header))
        self.assertEqual(len(ts.get_others_tasks_headers()), 2)

        self.assertIsNotNone(ts.add_task_header(task_header))
        self.assertEqual(len(ts.get_others_tasks_headers()), 2)

        new_header = dict(task_header)
        new_header["task_owner"]["pub_port"] = 9999
        new_header["signature"] = keys_auth_2.sign(
            TaskHeader.dict_to_binary(new_header))

        self.assertIsNotNone(ts.add_task_header(new_header))
        self.assertEqual(len(ts.get_others_tasks_headers()), 2)
        saved_task = next(th for th in ts.get_others_tasks_headers()
                          if th["task_id"] == task_id2)
        self.assertEqual(saved_task["signature"], new_header["signature"])

    def test_sync(self, *_):
        self.ts.sync_network()

    def test_forwarded_session_requests(self, *_):
        ts = self.ts
        ts.network = Mock()

        key_id = str(uuid.uuid4())
        conn_id = str(uuid.uuid4())
        subtask_id = str(uuid.uuid4())

        ts.add_forwarded_session_request(key_id, conn_id)
        self.assertEqual(len(ts.forwarded_session_requests), 1)

        ts.forwarded_session_requests[key_id]['time'] = 0
        ts._sync_forwarded_session_requests()
        self.assertEqual(len(ts.forwarded_session_requests), 0)

        ts.add_forwarded_session_request(key_id, conn_id)
        ts.forwarded_session_requests[key_id] = None
        ts._sync_forwarded_session_requests()
        self.assertEqual(len(ts.forwarded_session_requests), 0)

        session = MagicMock()
        session.address = '127.0.0.1'
        session.port = 65535

        ts.conn_established_for_type[TASK_CONN_TYPES['task_failure']](
            session, conn_id, key_id, subtask_id, "None"
        )
        self.assertEqual(ts.task_sessions[subtask_id], session)

    def test_retry_sending_task_result(self, *_):
        ts = self.ts
        ts.network = Mock()

        subtask_id = 'xxyyzz'
        wtr = Mock()
        wtr.already_sending = True

        ts.results_to_send[subtask_id] = wtr

        ts.retry_sending_task_result(subtask_id)
        self.assertFalse(wtr.already_sending)

    def test_send_waiting_results(self, *_):
        ts = self.ts
        ts.network = Mock()
        ts._mark_connected = Mock()
        ts.task_computer = Mock()
        ts.task_manager = Mock()
        ts.task_manager.check_timeouts.return_value = []
        ts.task_keeper = Mock()
        ts.task_connections_helper = Mock()
        ts._add_pending_request = Mock()

        subtask_id = 'xxyyzz'

        wtr = Mock()
        ts.results_to_send[subtask_id] = wtr

        wtr.already_sending = True
        wtr.last_sending_trial = 0
        wtr.delay_time = 0
        wtr.subtask_id = subtask_id
        wtr.address = '127.0.0.1'
        wtr.port = 10000

        ts.sync_network()
        ts._add_pending_request.assert_not_called()

        wtr.last_sending_trial = 0
        ts.retry_sending_task_result(subtask_id)

        ts.sync_network()
        self.assertEquals(ts._add_pending_request.call_count, 1)

        ts._add_pending_request.reset_mock()
        ts.task_sessions[subtask_id] = Mock()
        ts.task_sessions[subtask_id].last_message_time = float('infinity')

        ts.sync_network()
        ts._add_pending_request.assert_not_called()

        ts._add_pending_request.reset_mock()
        ts.results_to_send = dict()

        wtf = wtr

        ts.failures_to_send[subtask_id] = wtf
        ts.sync_network()
        ts._add_pending_request.assert_not_called()
        self.assertEqual(ts.failures_to_send, {})

        ts._add_pending_request.reset_mock()
        ts.task_sessions.pop(subtask_id)

        ts.failures_to_send[subtask_id] = wtf
        ts.sync_network()
        self.assertEquals(ts._add_pending_request.call_count, 1)
        self.assertEqual(ts.failures_to_send, {})

    def test_add_task_session(self, *_):
        ts = self.ts
        ts.network = Mock()

        session = Mock()
        subtask_id = 'xxyyzz'
        ts.add_task_session(subtask_id, session)
        self.assertIsNotNone(ts.task_sessions[subtask_id])

    def test_remove_task_session(self, *_):
        ts = self.ts
        ts.network = Mock()

        conn_id = str(uuid.uuid4())
        session = Mock()
        session.conn_id = conn_id

        ts.remove_task_session(session)
        ts.task_sessions['task'] = session
        ts.remove_task_session(session)

    def test_respond_to(self, *_):
        ts = self.ts
        ts.network = Mock()
        session = Mock()

        ts.respond_to('key_id', session, 'conn_id')
        self.assertTrue(session.dropped.called)

        session.dropped.called = False
        ts.response_list['conn_id'] = deque([lambda *_: lambda x: x])
        ts.respond_to('key_id', session, 'conn_id')
        self.assertFalse(session.dropped.called)

    def test_conn_for_task_failure_established(self, *_):
        ts = self.ts
        ts.network = Mock()
        session = Mock()
        session.address = '127.0.0.1'
        session.port = 40102

        method = ts._TaskServer__connection_for_task_failure_established
        method(session, 'conn_id', 'key_id', 'subtask_id', 'err_msg')

        self.assertEqual(session.key_id, 'key_id')
        self.assertIn('subtask_id', ts.task_sessions)
        self.assertTrue(session.send_hello.called)
        session.send_task_failure.assert_called_once_with('subtask_id',
                                                          'err_msg')

    def test_conn_for_start_session_failure(self, *_):
        ts = self.ts
        ts.network = Mock()
        ts.final_conn_failure = Mock()

        method = ts._TaskServer__connection_for_start_session_failure
        method('conn_id', 'key_id', Mock(), Mock(), 'ans_conn_id')

        ts.final_conn_failure.assert_called_with('conn_id')

    def test_conn_final_failures(self, *_):
        ts = self.ts
        ts.network = Mock()
        ts.final_conn_failure = Mock()
        ts.task_computer = Mock()

        ts.remove_pending_conn = Mock()
        ts.remove_responses = Mock()

        method = ts._TaskServer__connection_for_task_result_final_failure
        wtr = Mock()
        method('conn_id', wtr)

        self.assertTrue(ts.remove_pending_conn.called)
        self.assertTrue(ts.remove_responses.called)
        self.assertFalse(wtr.alreadySending)
        self.assertTrue(wtr.lastSendingTrial)

        ts.remove_pending_conn.called = False
        ts.remove_responses.called = False

        method = ts._TaskServer__connection_for_task_failure_final_failure
        method('conn_id', 'key_id', 'subtask_id', 'err_msg')

        self.assertTrue(ts.remove_pending_conn.called)
        self.assertTrue(ts.remove_responses.called)
        self.assertTrue(ts.task_computer.session_timeout.called)
        ts.remove_pending_conn.called = False
        ts.remove_responses.called = False
        ts.task_computer.session_timeout.called = False

        method = ts._TaskServer__connection_for_start_session_final_failure
        method('conn_id', 'key_id', Mock(), Mock(), 'ans_conn_id')

        self.assertTrue(ts.remove_pending_conn.called)
        self.assertTrue(ts.remove_responses.called)
        self.assertTrue(ts.task_computer.session_timeout.called)

        self.assertFalse(ts.task_computer.task_request_rejected.called)
        method = ts._TaskServer__connection_for_task_request_final_failure
        method('conn_id', 'node_name', 'key_id', 'task_id', 1000, 1000, 1000,
               1024, 3)
        self.assertTrue(ts.task_computer.task_request_rejected.called)

    def test_task_result_connection_failure(self, *_):
        """Tests what happens after connection failure when sending
        task_result"""
        node = Mock(
            key='deadbeef',
            prv_port=None,
            prv_addr='10.0.0.10',
        )
        ts = self.ts
        ts.network = MagicMock()
        ts.final_conn_failure = Mock()
        ts.task_computer = Mock()
        ts._is_address_accessible = Mock(return_value=True)

        # Always fail on listening
        from golem.network.transport import tcpnetwork
        ts.network.listen = MagicMock(
            side_effect=lambda listen_info, waiting_task_result:
            tcpnetwork.TCPNetwork.__call_failure_callback(  # noqa pylint: disable=too-many-function-args
                listen_info.failure_callback,
                {'waiting_task_result': waiting_task_result}
            )
        )
        # Try sending mocked task_result
        wtr = MagicMock(
            owner=node,
            owner_key_id='owner_key_id'
        )
        ts._add_pending_request(
            TASK_CONN_TYPES['task_result'],
            node,
            prv_port=node.prv_port,
            pub_port=node.pub_port,
            args={'waiting_task_result': wtr}
        )
        ts._sync_pending()
        assert not ts.network.connect.called

    def test_should_accept_provider(self, *_):
        ts = self.ts
        self.client.get_computing_trust = Mock(return_value=0.4)
        ts.config_desc.computing_trust = 0.2
        assert ts.should_accept_provider("ABC")
        ts.config_desc.computing_trust = 0.4
        assert ts.should_accept_provider("ABC")
        ts.config_desc.computing_trust = 0.5
        assert not ts.should_accept_provider("ABC")

        ts.config_desc.computing_trust = 0.2
        assert ts.should_accept_provider("ABC")

        ts.acl.disallow("ABC")
        assert not ts.should_accept_provider("ABC")

    def test_should_accept_requestor(self, *_):
        ts = self.ts
        self.client.get_requesting_trust = Mock(return_value=0.4)
        ts.config_desc.requesting_trust = 0.2
        assert ts.should_accept_requestor("ABC").is_ok()
        ts.config_desc.requesting_trust = 0.4
        assert ts.should_accept_requestor("ABC").is_ok()
        ts.config_desc.requesting_trust = 0.5
        ss = ts.should_accept_requestor("ABC")
        assert not ss.is_ok()
        assert UnsupportReason.REQUESTOR_TRUST in ss.desc
        self.assertEqual(ss.desc[UnsupportReason.REQUESTOR_TRUST], 0.4)

        ts.config_desc.requesting_trust = 0.2
        assert ts.should_accept_requestor("ABC").is_ok()

        ts.acl.disallow("ABC")
        ss = ts.should_accept_requestor("ABC")
        assert not ss.is_ok()
        assert UnsupportReason.DENY_LIST in ss.desc
        self.assertEqual(ss.desc[UnsupportReason.DENY_LIST], "ABC")

    @patch('golem.task.taskserver.TaskServer._mark_connected')
    def test_new_session_prepare(self, mark_mock, *_):
        session = tasksession.TaskSession(conn=MagicMock())
        session.address = '127.0.0.1'
        session.port = 10

        subtask_id = str(uuid.uuid4())
        key_id = str(uuid.uuid4())
        conn_id = str(uuid.uuid4())

        self.ts.new_session_prepare(
            session=session,
            subtask_id=subtask_id,
            key_id=key_id,
            conn_id=conn_id
        )
        self.assertEqual(session.task_id, subtask_id)
        self.assertEqual(session.key_id, key_id)
        self.assertEqual(session.conn_id, conn_id)
        mark_mock.assert_called_once_with(conn_id, session.address,
                                          session.port)

    def test_new_connection(self, *_):
        ts = self.ts
        tss = TaskSession(Mock())
        ts.new_connection(tss)
        assert len(ts.task_sessions_incoming) == 1
        assert ts.task_sessions_incoming.pop() == tss

    def test_download_options(self, *_):
        dm = DirManager(self.path)
        rm = HyperdriveResourceManager(dm)
        self.client.resource_server.resource_manager = rm
        ts = self.ts

        options = HyperdriveClientOptions(HyperdriveClient.CLIENT_ID,
                                          HyperdriveClient.VERSION)

        client_options = ts.get_download_options(options, task_id='task_id')
        assert client_options.peers is None

        peers = [
            to_hyperg_peer('127.0.0.1', 3282),
            to_hyperg_peer('127.0.0.1', 0),
            to_hyperg_peer('127.0.0.1', None),
            to_hyperg_peer('1.2.3.4', 3282),
            {'uTP': ('1.2.3.4', 3282)}
        ]

        options = HyperdriveClientOptions(HyperdriveClient.CLIENT_ID,
                                          HyperdriveClient.VERSION,
                                          options=dict(peers=peers))

        client_options = ts.get_download_options(options, task_id='task_id')
        assert client_options.options.get('peers') == [
            to_hyperg_peer('127.0.0.1', 3282),
            to_hyperg_peer('1.2.3.4', 3282),
        ]


class TestTaskServer2(TestDatabaseWithReactor, testutils.TestWithClient):
    def setUp(self):
        for parent in self.__class__.__bases__:
            parent.setUp(self)
        random.seed()
        self.ccd = self._get_config_desc()
        with patch(
                'golem.network.concent.handlers_library.HandlersLibrary'
                '.register_handler',):
            self.ts = TaskServer(
                node=Node(),
                config_desc=self.ccd,
                client=self.client,
                use_docker_manager=False,
            )
        self.ts.task_computer = MagicMock()

    def tearDown(self):
        for parent in self.__class__.__bases__:
            parent.tearDown(self)

    def test_find_sessions(self, *_):
        subtask_id = str(uuid.uuid4())

        # Empty
        self.assertEqual([], self.ts._find_sessions(subtask_id))

        # Found task_id
        task_id = 't' + str(uuid.uuid4())
        session = MagicMock()
        session.task_id = task_id
        self.ts.task_manager.subtask2task_mapping[subtask_id] = task_id
        self.ts.task_sessions_incoming.add(session)
        self.assertEqual([session], self.ts._find_sessions(subtask_id))

        # Found in task_sessions
        subtask_session = MagicMock()
        self.ts.task_sessions[subtask_id] = subtask_session
        self.assertEqual([subtask_session], self.ts._find_sessions(subtask_id))

    @patch("golem.task.taskmanager.TaskManager.dump_task")
    @patch("golem.task.taskserver.Trust")
    def test_results(self, trust, dump_mock, *_):
        ts = self.ts
        ts.task_manager.listen_port = 1111
        ts.task_manager.listen_address = "10.10.10.10"
        ts.receive_subtask_computation_time("xxyyzz", 1031)

        task_mock = get_mock_task("xyz", "xxyyzz")
        task_mock.get_trust_mod.return_value = ts.max_trust
        task_id = task_mock.header.task_id
        extra_data = Mock()
        extra_data.ctd = ComputeTaskDef()
        extra_data.ctd['task_id'] = task_mock.header.task_id
        extra_data.ctd['subtask_id'] = "xxyyzz"
        extra_data.should_wait = False
        task_mock.query_extra_data.return_value = extra_data

        ts.task_manager.add_new_task(task_mock)
        ts.task_manager.tasks_states[task_id].status = \
            ts.task_manager.activeStatus[0]
        subtask, wrong_task, wait = ts.task_manager.get_next_subtask(
            "DEF",
            "DEF",
            task_id,
            1000, 10,
            5, 10, 2,
            "10.10.10.10")
        ts.receive_subtask_computation_time("xxyyzz", 1031)
        self.assertEqual(ts.task_manager.tasks_states[task_id].subtask_states[
            "xxyyzz"].computation_time, 1031)
        expected_value = ceil(1031 * 1010 / 3600)
        task_state = ts.task_manager.tasks_states[task_id]
        self.assertEqual(task_state.subtask_states["xxyyzz"].value,
                         expected_value)
        account_info = Mock()
        account_info.key_id = "key"
        prev_calls = trust.COMPUTED.increase.call_count
        ts.accept_result("xxyyzz", account_info)
        ts.client.transaction_system.add_payment_info.assert_called_with(
            task_id,
            "xxyyzz",
            expected_value,
            account_info)
        self.assertGreater(trust.COMPUTED.increase.call_count, prev_calls)

    @patch("golem.task.taskmanager.TaskManager.dump_task")
    @patch("golem.task.taskserver.Trust")
    def test_results_no_payment_addr(self, *_):
        # FIXME: This test is too heavy, it starts up whole Golem Client.
        ts = self.ts
        ts.task_manager.listen_address = "10.10.10.10"
        ts.task_manager.listen_port = 1111
        ts.receive_subtask_computation_time("xxyyzz", 1031)

        extra_data = Mock()
        extra_data.ctd = ComputeTaskDef()
        extra_data.ctd['subtask_id'] = "xxyyzz"
        extra_data.should_wait = False

        task_mock = get_mock_task("xyz", "xxyyzz")
        task_id = task_mock.header.task_id
        task_mock.get_trust_mod.return_value = ts.max_trust
        extra_data.ctd['task_id'] = task_id
        task_mock.query_extra_data.return_value = extra_data

        ts.task_manager.add_new_task(task_mock)
        ts.task_manager.tasks_states[task_id].status = \
            ts.task_manager.activeStatus[0]
        subtask, wrong_task, wait = ts.task_manager.get_next_subtask(
            "DEF", "DEF", task_id, 1000, 10, 5, 10, 2, "10.10.10.10")

        ts.receive_subtask_computation_time("xxyyzz", 1031)
        account_info = Mock()
        account_info.key_id = "key"
        account_info.eth_account = Mock()
        account_info.eth_account.address = None

        ts.accept_result("xxyyzz", account_info)
        self.assertEqual(
            ts.client.transaction_system.add_payment_info.call_count, 0)

    def test_disconnect(self, *_):
        self.ts.task_sessions = {'task_id': Mock()}
        self.ts.disconnect()
        assert self.ts.task_sessions['task_id'].dropped.called

    def _get_config_desc(self):
        ccd = ClientConfigDescriptor()
        ccd.root_path = self.path
        return ccd


class TestRestoreResources(LogTestCase, testutils.DatabaseFixture,
                           testutils.TestWithClient):

    def setUp(self):
        for parent in self.__class__.__bases__:
            parent.setUp(self)

        self.resource_manager = Mock(
            add_task=Mock(side_effect=lambda *a, **b: ([], "a1b2c3"))
        )
        with patch(
                'golem.network.concent.handlers_library.HandlersLibrary'
                '.register_handler',):
            self.ts = TaskServer(
                node=Mock(),
                config_desc=ClientConfigDescriptor(),
                client=self.client,
                use_docker_manager=False,
            )
        self.ts.task_manager.notify_update_task = Mock(
            side_effect=self.ts.task_manager.notify_update_task
        )
        self.ts.task_manager.delete_task = Mock(
            side_effect=self.ts.task_manager.delete_task
        )
        self.ts._get_resource_manager = Mock(
            return_value=self.resource_manager
        )
        self.ts.task_manager.dump_task = Mock()
        self.task_count = 3

    @staticmethod
    def _create_tasks(task_server, count):
        for _ in range(count):
            task_id = str(uuid.uuid4())
            task = Mock()
            task.get_resources.return_value = []
            task_server.task_manager.tasks[task_id] = task
            task_server.task_manager.tasks_states[task_id] = TaskState()

    def test_without_tasks(self, *_):
        with patch.object(self.resource_manager, 'add_task',
                          side_effect=ConnectionError):
            self.ts.restore_resources()
            assert not self.resource_manager.add_task.called
            assert not self.ts.task_manager.delete_task.called
            assert not self.ts.task_manager.notify_update_task.called

    def test_with_connection_error(self, *_):
        self._create_tasks(self.ts, self.task_count)

        with patch.object(self.resource_manager, 'add_task',
                          side_effect=ConnectionError):
            self.ts.restore_resources()
            assert self.resource_manager.add_task.call_count == self.task_count
            assert self.ts.task_manager.delete_task.call_count == \
                self.task_count
            assert not self.ts.task_manager.notify_update_task.called

    def test_with_http_error(self, *_):
        self._create_tasks(self.ts, self.task_count)

        with patch.object(self.resource_manager, 'add_task',
                          side_effect=HTTPError):
            self.ts.restore_resources()
            assert self.resource_manager.add_task.call_count == self.task_count
            assert self.ts.task_manager.delete_task.call_count == \
                self.task_count
            assert not self.ts.task_manager.notify_update_task.called

    def test_with_http_error_and_resource_hashes(self, *_):
        self._test_with_error_and_resource_hashes(HTTPError)

    def test_with_resource_error_and_resource_hashes(self, *_):
        self._test_with_error_and_resource_hashes(ResourceError)

    def _test_with_error_and_resource_hashes(self, error_class):
        self._create_tasks(self.ts, self.task_count)
        for state in self.ts.task_manager.tasks_states.values():
            state.resource_hash = str(uuid.uuid4())

        with patch.object(self.resource_manager, 'add_task',
                          side_effect=error_class):
            self.ts.restore_resources()
            assert self.resource_manager.add_task.call_count ==\
                self.task_count * 2
            assert self.ts.task_manager.delete_task.call_count == \
                self.task_count
            assert not self.ts.task_manager.notify_update_task.called

    def test_restore_resources(self, *_):
        self._create_tasks(self.ts, self.task_count)

        self.ts.restore_resources()
        assert self.resource_manager.add_task.call_count == self.task_count
        assert not self.ts.task_manager.delete_task.called
        assert self.ts.task_manager.notify_update_task.call_count == \
            self.task_count
