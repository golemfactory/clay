from __future__ import division

from collections import deque
import datetime
from math import ceil
from mock import Mock, MagicMock, patch, ANY
import os
import random
from stun import FullCone
import uuid

from golem import model
from golem import testutils
from golem.core.common import timeout_to_deadline
from golem.core.keysauth import EllipticalKeysAuth
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.variables import APP_VERSION
from golem.network.p2p.node import Node
from golem.task import tasksession
from golem.task.taskbase import ComputeTaskDef, TaskHeader
from golem.task.taskserver import TaskServer, WaitingTaskResult, logger
from golem.task.taskserver import TASK_CONN_TYPES
from golem.tools.assertlogs import LogTestCase
from golem.tools.testwithappconfig import TestWithKeysAuth
from golem.tools.testwithreactor import TestDirFixtureWithReactor


def get_example_task_header():
    return {
        "task_id": "uvw",
        "node_name": "ABC",
        "environment": "DEFAULT",
        "task_owner": dict(),
        "task_owner_port": 10101,
        "task_owner_key_id": "key",
        "task_owner_address": "10.10.10.10",
        "deadline": timeout_to_deadline(1201),
        "subtask_timeout": 120,
        "max_price": 20,
        "resource_size": 2 * 1024,
        "estimated_memory": 3 * 1024,
        "signature": None,
        "min_version": APP_VERSION
    }


def get_mock_task(task_id, subtask_id):
    task_mock = Mock()
    task_mock.header = TaskHeader.from_dict(get_example_task_header())
    task_mock.header.task_id = task_id
    task_mock.header.max_price = 10000
    task_mock.query_extra_data.return_value.ctd.task_id = task_id
    task_mock.query_extra_data.return_value.ctd.subtask_id = subtask_id
    return task_mock


class TestTaskServer(TestWithKeysAuth, LogTestCase, testutils.DatabaseFixture):

    def setUp(self):
        for parent in self.__class__.__bases__:
            parent.setUp(self)
        random.seed()
        self.ccd = self._get_config_desc()
        self.ts = TaskServer(Node(), self.ccd, EllipticalKeysAuth(self.path),
                             self.client, use_docker_machine_manager=False)

    def tearDown(self):
        LogTestCase.tearDown(self)
        TestWithKeysAuth.tearDown(self)

        if hasattr(self, "ts") and self.ts:
            self.ts.quit()

    def test_request(self):
        ccd = self._get_config_desc()
        ccd.min_price = 10
        n = Node()
        ka = EllipticalKeysAuth(self.path)
        ts = TaskServer(n, ccd, ka, self.client,
                        use_docker_machine_manager=False)
        ts.verify_header_sig = lambda x: True
        self.ts = ts
        ts.client.get_suggested_addr.return_value = "10.10.10.10"
        ts.client.get_suggested_conn_reverse.return_value = False
        ts.client.get_requesting_trust.return_value = 0.3
        self.assertIsInstance(ts, TaskServer)
        self.assertIsNone(ts.request_task())
        n2 = Node()
        n2.prv_addr = "10.10.10.10"
        n2.port = 10101
        task_header = get_example_task_header()
        task_header["task_owner"] = n2
        ts.add_task_header(task_header)
        self.assertEqual(ts.request_task(), "uvw")
        ts.remove_task_header("uvw")
        task_header["task_owner_port"] = 0
        task_header["task_id"] = "uvw2"
        self.assertTrue(ts.add_task_header(task_header))
        self.assertIsNotNone(ts.task_keeper.task_headers["uvw2"])
        self.assertIsNone(ts.request_task())
        self.assertIsNone(ts.task_keeper.task_headers.get("uvw2"))

    @patch("golem.task.taskserver.Trust")
    def test_send_results(self, trust):
        ccd = self._get_config_desc()
        ccd.min_price = 11
        n = Node()
        ka = EllipticalKeysAuth(self.path)
        ts = TaskServer(n, ccd, ka, self.client,
                        use_docker_machine_manager=False)
        ts.verify_header_sig = lambda x: True
        self.ts = ts
        ts.client.get_suggested_addr.return_value = "10.10.10.10"
        results = {"data": "", "result_type": 0}
        task_header = get_example_task_header()
        task_header["task_id"] = "xyz"
        ts.add_task_header(task_header)
        ts.request_task()
        self.assertTrue(ts.send_results("xxyyzz", "xyz", results, 40, "10.10.10.10", 10101, "key", n, "node_name"))
        ts.client.transaction_system.incomes_keeper.expect.reset_mock()
        self.assertTrue(ts.send_results("xyzxyz", "xyz", results, 40, "10.10.10.10", 10101, "key", n, "node_name"))
        self.assertEqual(ts.get_subtask_ttl("xyz"), 120)
        wtr = ts.results_to_send["xxyyzz"]
        self.assertIsInstance(wtr, WaitingTaskResult)
        self.assertEqual(wtr.subtask_id, "xxyyzz")
        self.assertEqual(wtr.result, "")
        self.assertEqual(wtr.result_type, 0)
        self.assertEqual(wtr.computing_time, 40)
        self.assertEqual(wtr.last_sending_trial, 0)
        self.assertEqual(wtr.delay_time, 0)
        self.assertEqual(wtr.owner_address, "10.10.10.10")
        self.assertEqual(wtr.owner_port, 10101)
        self.assertEqual(wtr.owner_key_id, "key")
        self.assertEqual(wtr.owner, n)
        self.assertEqual(wtr.already_sending, False)
        ts.client.transaction_system.incomes_keeper.expect.assert_called_once_with(
            sender_node_id="key",
            task_id="xyz",
            subtask_id="xyzxyz",
            value=1,
            p2p_node=n,
        )

        with self.assertLogs(logger, level='WARNING'):
            ts.subtask_rejected("aabbcc")
        self.assertIsNotNone(ts.task_keeper.task_headers.get("xyz"))

        prev_call_count = trust.PAYMENT.increase.call_count
        with self.assertLogs(logger, level="WARNING"):
            ts.reward_for_subtask_paid(subtask_id="aa2bb2cc", reward=1,
                                       transaction_id=None, block_number=None)
        ts.client.transaction_system.incomes_keeper.received.assert_not_called()
        self.assertEqual(trust.PAYMENT.increase.call_count, prev_call_count)

        ctd = ComputeTaskDef()
        ctd.task_id = "xyz"
        ctd.subtask_id = "xxyyzz"
        ts.task_manager.comp_task_keeper.receive_subtask(ctd)
        model.ExpectedIncome.create(
            sender_node="key",
            sender_node_details=None,
            task=ctd.task_id,
            subtask=ctd.subtask_id,
            value=1
        )
        ts.reward_for_subtask_paid(subtask_id="xxyyzz", reward=1,
                                   transaction_id=None, block_number=None)
        self.assertGreater(trust.PAYMENT.increase.call_count, prev_call_count)
        prev_call_count = trust.PAYMENT.increase.call_count
        ts.increase_trust_payment("xyz")
        self.assertGreater(trust.PAYMENT.increase.call_count, prev_call_count)
        prev_call_count = trust.PAYMENT.decrease.call_count
        ts.decrease_trust_payment("xyz")
        self.assertGreater(trust.PAYMENT.decrease.call_count, prev_call_count)

    def test_connection_for_task_request_established(self):
        ccd = self._get_config_desc()
        ccd.min_price = 11
        n = Node()
        ka = EllipticalKeysAuth(self.path)
        ts = TaskServer(n, ccd, ka, self.client,
                        use_docker_machine_manager=False)
        self.ts = ts
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
        session.request_task.assert_called_with("nodename", "xyz", 1010, 30, 3, 1, 2)

    def test_change_config(self):
        ccd = self._get_config_desc()
        ccd.task_session_timeout = 40
        ccd.min_price = 1.0
        ccd.use_distributed_resource_management = 10
        ccd.task_request_interval = 10
        # ccd.use_waiting_ttl = True
        ccd.waiting_for_task_timeout = 19

        ts = TaskServer(Node(), ccd, EllipticalKeysAuth(self.path), self.client,
                        use_docker_machine_manager=False)
        self.ts = ts

        ccd2 = self._get_config_desc()
        ccd2.task_session_timeout = 124
        ccd2.min_price = 0.0057
        ccd2.use_distributed_resource_management = 0
        ccd2.task_request_interval = 31
        # ccd2.use_waiting_ttl = False
        ccd2.waiting_for_task_timeout = 90
        ts.change_config(ccd2)
        self.assertEqual(ts.config_desc, ccd2)
        self.assertEqual(ts.last_message_time_threshold, 124)
        self.assertEqual(ts.task_keeper.min_price, 0.0057)
        self.assertEqual(ts.task_manager.use_distributed_resources, False)
        self.assertEqual(ts.task_computer.task_request_frequency, 31)
        self.assertEqual(ts.task_computer.waiting_for_task_timeout, 90)
        # self.assertEqual(ts.task_computer.use_waiting_ttl, False)

    def test_add_task_header(self):
        config = self._get_config_desc()
        keys_auth = EllipticalKeysAuth(self.path)
        keys_auth_2 = EllipticalKeysAuth(os.path.join(self.path, "2"))

        self.ts = ts = TaskServer(Node(), config, keys_auth, self.client,
                                  use_docker_machine_manager=False)

        task_header = get_example_task_header()
        task_header["task_id"] = "xyz"

        with self.assertRaises(Exception) as raised:
            ts.add_task_header(task_header)
            self.assertEqual(raised.exception.message, "Invalid signature")
            self.assertEqual(len(ts.get_tasks_headers()), 0)

        task_header["task_owner_key_id"] = keys_auth_2.key_id
        task_header["signature"] = keys_auth_2.sign(TaskHeader.dict_to_binary(task_header))

        self.assertIsNotNone(ts.add_task_header(task_header))
        self.assertEqual(len(ts.get_tasks_headers()), 1)

        task_header = get_example_task_header()
        task_header["task_id"] = "xyz_2"
        task_header["task_owner_key_id"] = keys_auth_2.key_id
        task_header["signature"] = keys_auth_2.sign(TaskHeader.dict_to_binary(task_header))

        self.assertIsNotNone(ts.add_task_header(task_header))
        self.assertEqual(len(ts.get_tasks_headers()), 2)

        self.assertIsNotNone(ts.add_task_header(task_header))
        self.assertEqual(len(ts.get_tasks_headers()), 2)

        new_header = dict(task_header)
        new_header["task_owner"]["pub_port"] = 9999
        new_header["signature"] = keys_auth_2.sign(TaskHeader.dict_to_binary(new_header))

        self.assertIsNotNone(ts.add_task_header(new_header))
        self.assertEqual(len(ts.get_tasks_headers()), 2)
        saved_task = next(th for th in ts.get_tasks_headers() if th["task_id"] == "xyz_2")
        self.assertEqual(saved_task["signature"], new_header["signature"])

    def test_sync(self):
        ccd = self._get_config_desc()
        ts = TaskServer(Node(), ccd, EllipticalKeysAuth(self.path), self.client,
                        use_docker_machine_manager=False)
        self.ts = ts
        ts.sync_network()

    def test_traverse_nat(self):
        ccd = self._get_config_desc()
        ts = TaskServer(Node(), ccd, EllipticalKeysAuth(self.path), self.client,
                        use_docker_machine_manager=False)
        self.ts = ts
        ts.network = Mock()
        ts.traverse_nat("ABC", "10.10.10.10", 1312, 310319041904, "DEF")
        self.assertEqual(ts.network.connect.call_args[0][0].socket_addresses[0].address, "10.10.10.10")
        self.assertEqual(ts.network.connect.call_args[0][0].socket_addresses[0].port, 1312)

    def test_forwarded_session_requests(self):
        ccd = self._get_config_desc()
        ts = TaskServer(Node(), ccd, EllipticalKeysAuth(self.path), self.client,
                        use_docker_machine_manager=False)
        self.ts = ts
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

    def test_retry_sending_task_result(self):
        ccd = self._get_config_desc()
        ts = TaskServer(Node(), ccd, EllipticalKeysAuth(self.path), self.client,
                        use_docker_machine_manager=False)
        self.ts = ts
        ts.network = Mock()

        subtask_id = 'xxyyzz'
        wtr = Mock()
        wtr.already_sending = True

        ts.results_to_send[subtask_id] = wtr

        ts.retry_sending_task_result(subtask_id)
        self.assertFalse(wtr.already_sending)

    def test_send_waiting_results(self):
        ccd = self._get_config_desc()
        ts = TaskServer(Node(), ccd, Mock(), self.client,
                        use_docker_machine_manager=False)
        self.ts = ts
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
        ts._add_pending_request.assert_called()

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
        ts._add_pending_request.assert_called()
        self.assertEqual(ts.failures_to_send, {})

    def test_add_task_session(self):
        ccd = self._get_config_desc()
        ts = TaskServer(Node(), ccd, Mock(), self.client,
                        use_docker_machine_manager=False)
        self.ts = ts
        ts.network = Mock()

        session = Mock()
        subtask_id = 'xxyyzz'
        ts.add_task_session(subtask_id, session)
        self.assertIsNotNone(ts.task_sessions[subtask_id])

    def test_initiate_nat_traversal(self):
        ccd = self._get_config_desc()
        node = Node()
        node.nat_type = FullCone

        ts = TaskServer(node, ccd, Mock(), self.client,
                        use_docker_machine_manager=False)
        self.ts = ts
        ts.network = Mock()
        ts._add_pending_request = Mock()

        initiate = ts._TaskServer__initiate_nat_traversal

        key_id = 'key_id'
        node_info = {}
        super_node_info = Mock()
        ans_conn_id = 'conn_id'

        initiate(key_id, node_info, None, ans_conn_id)
        self.assertFalse(ts._add_pending_request.called)

        initiate(key_id, node_info, super_node_info, ans_conn_id)
        ts._add_pending_request.assert_called_with(TASK_CONN_TYPES['nat_punch'],
                                                   ANY, ANY, ANY, ANY)

        node.nat_type = None
        initiate(key_id, node_info, super_node_info, ans_conn_id)
        ts._add_pending_request.assert_called_with(TASK_CONN_TYPES['middleman'],
                                                   ANY, ANY, ANY, ANY)

    def test_remove_task_session(self):
        ccd = self._get_config_desc()
        ts = TaskServer(Node(), ccd, Mock(), self.client,
                        use_docker_machine_manager=False)
        self.ts = ts
        ts.network = Mock()

        conn_id = str(uuid.uuid4())
        session = Mock()
        session.conn_id = conn_id

        ts.remove_task_session(session)
        ts.task_sessions['task'] = session
        ts.remove_task_session(session)

    def test_respond_to(self):
        ccd = self._get_config_desc()
        ts = TaskServer(Node(), ccd, Mock(), self.client,
                        use_docker_machine_manager=False)
        self.ts = ts
        ts.network = Mock()
        session = Mock()

        ts.respond_to('key_id', session, 'conn_id')
        self.assertTrue(session.dropped.called)

        session.dropped.called = False
        ts.response_list['conn_id'] = deque([lambda *_: lambda x: x])
        ts.respond_to('key_id', session, 'conn_id')
        self.assertFalse(session.dropped.called)

    def test_conn_for_task_failure_established(self):
        ccd = self._get_config_desc()
        ts = TaskServer(Node(), ccd, Mock(), self.client,
                        use_docker_machine_manager=False)
        self.ts = ts
        ts.network = Mock()
        session = Mock()
        session.address = '127.0.0.1'
        session.port = 40102

        method = ts._TaskServer__connection_for_task_failure_established
        method(session, 'conn_id', 'key_id', 'subtask_id', 'err_msg')

        self.assertEqual(session.key_id, 'key_id')
        self.assertIn('subtask_id', ts.task_sessions)
        self.assertTrue(session.send_hello.called)
        session.send_task_failure.assert_called_once_with('subtask_id', 'err_msg')

    def test_conn_for_start_session_failure(self):

        ccd = self._get_config_desc()
        ts = TaskServer(Node(), ccd, Mock(), self.client,
                        use_docker_machine_manager=False)
        self.ts = ts
        ts.network = Mock()
        ts.final_conn_failure = Mock()

        method = ts._TaskServer__connection_for_start_session_failure
        method('conn_id', 'key_id', Mock(), Mock(), 'ans_conn_id')

        ts.final_conn_failure.assert_called_with('conn_id')

    def test_conn_final_failures(self):

        ccd = self._get_config_desc()
        ts = TaskServer(Node(), ccd, Mock(), self.client,
                        use_docker_machine_manager=False)
        self.ts = ts
        ts.network = Mock()
        ts.final_conn_failure = Mock()
        ts.task_computer = Mock()

        method = ts._TaskServer__connection_for_resource_request_final_failure
        method('conn_id', 'key_id', 'subtask_id', Mock())

        ts.task_computer.resource_request_rejected.assert_called_once_with('subtask_id', ANY)

        ts.remove_pending_conn = Mock()
        ts.remove_responses = Mock()

        method = ts._TaskServer__connection_for_result_rejected_final_failure
        method('conn_id', 'key_id', 'subtask_id')

        self.assertTrue(ts.remove_pending_conn.called)
        self.assertTrue(ts.remove_responses.called_)
        ts.remove_pending_conn.called = False
        ts.remove_responses.called = False

        method = ts._TaskServer__connection_for_task_result_final_failure
        wtr = Mock()
        method('conn_id', 'key_id', wtr)

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

    def test_task_result_connection_failure(self):
        """Tests what happens after connection failure when sending task_result"""
        ccd = self._get_config_desc()
        ts = TaskServer(Node(), ccd, Mock(), self.client, use_docker_machine_manager=False)
        ts.network = MagicMock()
        ts.final_conn_failure = Mock()
        ts.task_computer = Mock()

        # Always fail on listening
        from golem.network.transport import tcpnetwork
        ts.network.listen = MagicMock(
            side_effect=lambda listen_info, waiting_task_result:
                tcpnetwork.TCPNetwork.__call_failure_callback(
                    listen_info.failure_callback,
                    {'waiting_task_result': waiting_task_result}
                )
        )

        # Try sending mocked task_result
        wtr = MagicMock()
        wtr.owner_key_id = 'owner_key_id'
        kwargs = {'waiting_task_result': wtr}
        ts._add_pending_request(TASK_CONN_TYPES['task_result'], 'owner_id', 'owner_port', wtr.owner_key_id, kwargs)
        ts._sync_pending()
        ts.client.want_to_start_task_session.assert_called_once_with(
            wtr.owner_key_id,
            ts.node,
            ANY,  # conn_id
        )

    def _get_config_desc(self):
        ccd = ClientConfigDescriptor()
        ccd.root_path = self.path
        ccd.estimated_lux_performance = 2000.0
        ccd.estimated_blender_performance = 2000.0
        return ccd

    def test_should_accept_provider(self):
        ccd = self._get_config_desc()
        ts = TaskServer(Node(), ccd, Mock(), self.client,
                        use_docker_machine_manager=False)
        self.client.get_computing_trust = Mock(return_value=0.4)
        ts.config_desc.computing_trust = 0.2
        assert ts.should_accept_provider("ABC")
        ts.config_desc.computing_trust = 0.4
        assert ts.should_accept_provider("ABC")
        ts.config_desc.computing_trust = 0.5
        assert not ts.should_accept_provider("ABC")

        ts.config_desc.computing_trust = 0.2
        assert ts.should_accept_provider("ABC")

        ts.deny_set.add("ABC")
        assert not ts.should_accept_provider("ABC")

    def test_should_accept_requestor(self):
        ccd = self._get_config_desc()
        ts = TaskServer(Node(), ccd, Mock(), self.client,
                        use_docker_machine_manager=False)
        self.client.get_requesting_trust = Mock(return_value=0.4)
        ts.config_desc.rquesting_trust = 0.2
        assert ts.should_accept_requestor("ABC")
        ts.config_desc.requesting_trust = 0.4
        assert ts.should_accept_requestor("ABC")
        ts.config_desc.requesting_trust = 0.5
        assert not ts.should_accept_requestor("ABC")

        ts.config_desc.requesting_trust = 0.2
        assert ts.should_accept_requestor("ABC")

        ts.deny_set.add("ABC")
        assert not ts.should_accept_requestor("ABC")

    @patch('golem.task.taskserver.TaskServer._mark_connected')
    def test_new_session_prepare(self, mark_mock):
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
        self.assertEquals(session.task_id, subtask_id)
        self.assertEquals(session.key_id, key_id)
        self.assertEquals(session.conn_id, conn_id)
        mark_mock.assert_called_once_with(conn_id, session.address, session.port)

    @patch('golem.task.taskserver.TaskServer.new_session_prepare')
    @patch('golem.task.tasksession.TaskSession.send_hello')
    @patch('golem.task.tasksession.TaskSession.inform_worker_about_payment')
    def test_connection_for_payment(self, inform_mock, hello_mock,
                                    new_session_mock):
        session = tasksession.TaskSession(conn=MagicMock())
        session.address = '127.0.0.1'
        session.port = 10
        conn_id = str(uuid.uuid4())
        node = Node()
        payment = model.Payment.create(
            subtask=str(uuid.uuid4()),
            payee=str(uuid.uuid4()),
            value=random.randint(1, 10),
            details={'node_info': node, }
        )
        self.ts.connection_for_payment_established(session, conn_id, payment)
        new_session_mock.assert_called_once_with(
            session=session,
            subtask_id=payment.subtask,
            key_id=node.key,
            conn_id=conn_id
        )
        inform_mock.assert_called_once_with(payment)
        hello_mock.assert_called_once_with()

    @patch('golem.task.taskserver.TaskServer.new_session_prepare')
    @patch('golem.task.tasksession.TaskSession.send_hello')
    @patch('golem.task.tasksession.TaskSession.request_payment')
    def test_connection_for_payment_request(self, request_payment_mock,
                                            hello_mock, new_session_mock):
        session = tasksession.TaskSession(conn=MagicMock())
        session.address = '127.0.0.1'
        session.port = 10
        conn_id = str(uuid.uuid4())
        node = Node()
        expected_income = model.ExpectedIncome.create(
            sender_node=str(uuid.uuid4()),
            sender_node_details=node,
            value=random.randint(1, 10),
            subtask=str(uuid.uuid4()),
            task=str(uuid.uuid4())
        )
        self.ts.connection_for_payment_request_established(session, conn_id,
                                                           expected_income)
        new_session_mock.assert_called_once_with(
            session=session,
            subtask_id=expected_income.subtask,
            key_id=node.key,
            conn_id=conn_id
        )
        request_payment_mock.assert_called_once_with(expected_income)
        hello_mock.assert_called_once_with()


class TestTaskServer2(TestWithKeysAuth, TestDirFixtureWithReactor):

    def setUp(self):
        for parent in self.__class__.__bases__:
            parent.setUp(self)
        random.seed()
        self.ccd = self._get_config_desc()
        self.ts = TaskServer(Node(), self.ccd, EllipticalKeysAuth(self.path),
                             self.client, use_docker_machine_manager=False)
        self.ts.task_computer = MagicMock()

    def tearDown(self):
        for parent in self.__class__.__bases__:
            parent.tearDown(self)

    def test_find_sessions(self):
        subtask_id = str(uuid.uuid4())

        # Empty
        self.assertEquals([], self.ts._find_sessions(subtask_id))

        # Found task_id
        task_id = 't' + str(uuid.uuid4())
        session = MagicMock()
        session.task_id = task_id
        self.ts.task_manager.subtask2task_mapping[subtask_id] = task_id
        self.ts.task_sessions_incoming.append(session)
        self.assertEquals([session], self.ts._find_sessions(subtask_id))

        # Found in task_sessions
        subtask_session = MagicMock()
        self.ts.task_sessions[subtask_id] = subtask_session
        self.assertEquals([subtask_session], self.ts._find_sessions(subtask_id))

    @patch("golem.task.taskserver.TaskServer._add_pending_request")
    @patch("golem.task.taskserver.TaskServer._find_sessions")
    def test_send_waiting(self, find_sessions_mock, add_pending_mock):
        session_cbk = MagicMock()
        elem = MagicMock()
        elem.subtask_id = 's' + str(uuid.uuid4())
        elem.p2p_node = MagicMock()
        kwargs = {
            'elems_set': {elem},
            'subtask_id_getter': lambda x: x.subtask_id,
            'req_type': 'TEST_REQUEST_TYPE',
            'session_cbk': session_cbk,
            'p2p_node_getter': lambda x: x.p2p_node,
        }

        elem._last_try = datetime.datetime.now()
        self.ts._send_waiting(**kwargs)
        find_sessions_mock.assert_not_called()

        find_sessions_mock.return_value = []
        elem._last_try = datetime.datetime.min
        self.ts._send_waiting(**kwargs)
        find_sessions_mock.assert_called_once_with(elem.subtask_id)
        find_sessions_mock.reset_mock()
        add_pending_mock.assert_called_once_with(
            req_type=kwargs['req_type'],
            task_owner=elem.p2p_node,
            port=elem.p2p_node.prv_port,
            key_id=ANY,
            args={'obj': elem}
        )
        add_pending_mock.reset_mock()

        # Test ordinary session
        session = tasksession.TaskSession(conn=MagicMock())
        find_sessions_mock.return_value = [session]
        elem._last_try = datetime.datetime.min
        self.ts._send_waiting(**kwargs)
        find_sessions_mock.assert_called_once_with(elem.subtask_id)
        find_sessions_mock.reset_mock()
        session_cbk.assert_called_once_with(session, elem)
        session_cbk.reset_mock()
        self.assertEquals(0, len(kwargs['elems_set']))

        # Test weakref session exists
        import weakref
        find_sessions_mock.return_value = [weakref.ref(session)]
        elem._last_try = datetime.datetime.min
        kwargs['elems_set'] = {elem}
        self.ts._send_waiting(**kwargs)
        find_sessions_mock.assert_called_once_with(elem.subtask_id)
        find_sessions_mock.reset_mock()
        session_cbk.assert_called_once_with(session, elem)
        session_cbk.reset_mock()
        self.assertEquals(0, len(kwargs['elems_set']))

    @patch("golem.task.taskmanager.TaskManager.dump_task")
    @patch("golem.task.taskmanager.get_external_address")
    @patch("golem.task.taskserver.Trust")
    def test_results(self, trust, mock_addr, dump_mock):
        mock_addr.return_value = ("10.10.10.10", 1111, "Full NAT")
        ccd = self._get_config_desc()
        ts = TaskServer(Node(), ccd, EllipticalKeysAuth(self.path), self.client,
                        use_docker_machine_manager=False)
        self.ts = ts
        ts.task_manager.listen_port = 1111
        ts.task_manager.listen_address = "10.10.10.10"
        ts.receive_subtask_computation_time("xxyyzz", 1031)

        extra_data = Mock()
        extra_data.ctd = ComputeTaskDef()
        extra_data.ctd.task_id = "xyz"
        extra_data.ctd.subtask_id = "xxyyzz"
        extra_data.ctd.environment = "DEFAULT"
        extra_data.should_wait = False

        task_mock = get_mock_task("xyz", "xxyyzz")
        task_mock.query_extra_data.return_value = extra_data

        ts.task_manager.add_new_task(task_mock)
        ts.task_manager.tasks_states["xyz"].status = ts.task_manager.activeStatus[0]
        subtask, wrong_task, wait = ts.task_manager.get_next_subtask("DEF", "DEF", "xyz",
                                                                     1000, 10, 5, 10, 2,
                                                                     "10.10.10.10")
        ts.receive_subtask_computation_time("xxyyzz", 1031)
        self.assertEqual(ts.task_manager.tasks_states["xyz"].subtask_states["xxyyzz"].computation_time, 1031)
        expected_value = ceil(1031 * 10 / 3600)
        self.assertEqual(ts.task_manager.tasks_states["xyz"].subtask_states["xxyyzz"].value, expected_value)
        account_info = Mock()
        account_info.key_id = "key"
        prev_calls = trust.COMPUTED.increase.call_count
        ts.accept_result("xxyyzz", account_info)
        ts.client.transaction_system.add_payment_info.assert_called_with("xyz", "xxyyzz", expected_value, account_info)
        self.assertGreater(trust.COMPUTED.increase.call_count, prev_calls)

    @patch("golem.task.taskmanager.TaskManager.dump_task")
    @patch("golem.task.taskmanager.get_external_address")
    @patch("golem.task.taskserver.Trust")
    def test_results_no_payment_addr(self, trust, mock_addr, dump_mock):
        mock_addr.return_value = ("10.10.10.10", 1111, "Full NAT")
        # FIXME: This test is too heavy, it starts up whole Golem Client.
        ccd = self._get_config_desc()
        ts = TaskServer(Node(), ccd, EllipticalKeysAuth(self.path), self.client,
                        use_docker_machine_manager=False)
        ts.task_manager.listen_address = "10.10.10.10"
        ts.task_manager.listen_port = 1111
        ts.receive_subtask_computation_time("xxyyzz", 1031)

        self.ts = ts

        extra_data = Mock()
        extra_data.ctd = ComputeTaskDef()
        extra_data.ctd.task_id = "xyz"
        extra_data.ctd.subtask_id = "xxyyzz"
        extra_data.ctd.environment = "DEFAULT"
        extra_data.should_wait = False

        task_mock = get_mock_task("xyz", "xxyyzz")
        task_mock.query_extra_data.return_value = extra_data

        ts.task_manager.add_new_task(task_mock)
        ts.task_manager.tasks_states["xyz"].status = ts.task_manager.activeStatus[0]
        subtask, wrong_task, wait = ts.task_manager.get_next_subtask(
            "DEF", "DEF", "xyz", 1000, 10, 5, 10, 2, "10.10.10.10")

        ts.receive_subtask_computation_time("xxyyzz", 1031)
        account_info = Mock()
        account_info.key_id = "key"
        account_info.eth_account = Mock()
        account_info.eth_account.address = None

        ts.accept_result("xxyyzz", account_info)
        self.assertEqual(ts.client.transaction_system.add_payment_info.call_count, 0)

    def _get_config_desc(self):
        ccd = ClientConfigDescriptor()
        ccd.root_path = self.path
        ccd.estimated_lux_performance = 2000.0
        ccd.estimated_blender_performance = 2000.0
        return ccd
