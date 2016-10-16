from __future__ import division
import uuid
from collections import deque

from math import ceil
from mock import Mock, MagicMock, patch, ANY

from stun import FullCone

from golem.core.common import timeout_to_deadline
from golem.core.keysauth import EllipticalKeysAuth
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.network.p2p.node import Node
from golem.task.taskbase import ComputeTaskDef, TaskHeader
from golem.task.taskserver import TaskServer, WaitingTaskResult, TaskConnTypes, logger
from golem.tools.assertlogs import LogTestCase
from golem.tools.testwithappconfig import TestWithKeysAuth


class TestTaskServer(TestWithKeysAuth, LogTestCase):

    def tearDown(self):
        LogTestCase.tearDown(self)
        TestWithKeysAuth.tearDown(self)

        if hasattr(self, "ts") and self.ts:
            self.ts.quit()

    def test_request(self):
        ccd = self.__get_config_desc()
        ccd.min_price = 10
        n = Node()
        ka = EllipticalKeysAuth(self.path)
        ts = TaskServer(n, ccd, ka, self.client,
                        use_docker_machine_manager=False)
        ts.verify_header_sig = lambda x: True
        self.ts = ts
        ts.client.get_suggested_addr.return_value = "10.10.10.10"
        ts.client.get_suggested_conn_reverse.return_value = False
        self.assertIsInstance(ts, TaskServer)
        assert ts.request_task() is None
        n2 = Node()
        n2.prv_addr = "10.10.10.10"
        n2.port = 10101
        task_header = self.__get_example_task_header()
        task_header["task_owner"] = n2
        ts.add_task_header(task_header)
        assert ts.request_task() == "uvw"
        ts.remove_task_header("uvw")
        task_header["task_owner_port"] = 0
        task_header["task_id"] = "uvw2"
        assert ts.add_task_header(task_header)
        assert ts.task_keeper.task_headers["uvw2"] is not None
        assert ts.request_task() is None
        assert ts.task_keeper.task_headers.get("uvw2") is None

    def test_send_results(self):
        ccd = self.__get_config_desc()
        ccd.min_price = 11
        n = Node()
        ka = EllipticalKeysAuth(self.path)
        ts = TaskServer(n, ccd, ka, self.client,
                        use_docker_machine_manager=False)
        ts.verify_header_sig = lambda x: True
        self.ts = ts
        ts.client.get_suggested_addr.return_value = "10.10.10.10"
        results = {"data": "", "result_type": 0}
        task_header = self.__get_example_task_header()
        task_header["task_id"] = "xyz"
        ts.add_task_header(task_header)
        ts.request_task()
        self.assertTrue(ts.send_results("xxyyzz", "xyz", results, 40, "10.10.10.10", 10101, "key", n, "node_name"))
        self.assertTrue(ts.send_results("xyzxyz", "xyz", results, 40, "10.10.10.10", 10101, "key", n, "node_name"))
        assert ts.get_subtask_ttl("xyz") == 120
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
        ts.client.transaction_system.add_to_waiting_payments.assert_called_with(
            "xyz", "key", 1)

        with self.assertLogs(logger, level='WARNING'):
            ts.subtask_rejected("aabbcc")
        self.assertIsNotNone(ts.task_keeper.task_headers.get("xyz"))

        prev_call_count = ts.client.increase_trust.call_count
        with self.assertLogs(logger, level="WARNING"):
            ts.reward_for_subtask_paid("aa2bb2cc")
        self.assertEqual(ts.client.increase_trust.call_count, prev_call_count)

        ctd = ComputeTaskDef()
        ctd.task_id = "xyz"
        ctd.subtask_id = "xxyyzz"
        ts.task_manager.comp_task_keeper.receive_subtask(ctd)
        ts.reward_for_subtask_paid("xxyyzz")
        self.assertGreater(ts.client.increase_trust.call_count, prev_call_count)
        prev_call_count = ts.client.increase_trust.call_count
        ts.increase_trust_payment("xyz")
        self.assertGreater(ts.client.increase_trust.call_count, prev_call_count)
        prev_call_count = ts.client.decrease_trust.call_count
        ts.decrease_trust_payment("xyz")
        self.assertGreater(ts.client.decrease_trust.call_count, prev_call_count)

    def test_connection_for_task_request_established(self):
        ccd = self.__get_config_desc()
        ccd.min_price = 11
        n = Node()
        ka = EllipticalKeysAuth(self.path)
        ts = TaskServer(n, ccd, ka, self.client,
                        use_docker_machine_manager=False)
        self.ts = ts
        session = Mock()
        session.address = "10.10.10.10"
        session.port = 1020
        ts.conn_established_for_type[TaskConnTypes.TaskRequest](session, "abc", "nodename", "key", "xyz", 1010, 30, 3,
                                                                1, 2)
        self.assertEqual(session.task_id, "xyz")
        self.assertEqual(session.key_id, "key")
        self.assertEqual(session.conn_id, "abc")
        self.assertEqual(ts.task_sessions["xyz"], session)
        session.send_hello.assert_called_with()
        session.request_task.assert_called_with("nodename", "xyz", 1010, 30, 3, 1, 2)

    def test_change_config(self):
        ccd = self.__get_config_desc()
        ccd.task_session_timeout = 40
        ccd.min_price = 1.0
        ccd.use_distributed_resource_management = 10
        ccd.task_request_interval = 10
        # ccd.use_waiting_ttl = True
        ccd.waiting_for_task_timeout = 19

        ts = TaskServer(Node(), ccd, EllipticalKeysAuth(self.path), self.client,
                        use_docker_machine_manager=False)
        self.ts = ts

        ccd2 = self.__get_config_desc()
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
        config = self.__get_config_desc()
        keys_auth = EllipticalKeysAuth(self.path)

        self.ts = ts = TaskServer(Node(), config, keys_auth, self.client,
                                  use_docker_machine_manager=False)

        task_header = self.__get_example_task_header()
        task_header["task_id"] = "xyz"

        with self.assertRaises(Exception) as raised:
            ts.add_task_header(task_header)
            assert raised.exception.message == "Invalid signature"
        assert len(ts.get_tasks_headers()) == 0

        task_header["task_owner_key_id"] = keys_auth.key_id
        task_header["signature"] = keys_auth.sign(TaskHeader.dict_to_binary(task_header))

        ts.add_task_header(task_header)
        assert len(ts.get_tasks_headers()) == 1

        task_header = self.__get_example_task_header()
        task_header["task_id"] = "xyz_2"
        task_header["task_owner_key_id"] = keys_auth.key_id
        task_header["signature"] = keys_auth.sign(TaskHeader.dict_to_binary(task_header))

        ts.add_task_header(task_header)
        assert len(ts.get_tasks_headers()) == 2

    def test_sync(self):
        ccd = self.__get_config_desc()
        ts = TaskServer(Node(), ccd, EllipticalKeysAuth(self.path), self.client,
                        use_docker_machine_manager=False)
        self.ts = ts
        ts.sync_network()

    @patch("golem.task.taskmanager.get_external_address")
    def test_results(self, mock_addr):
        mock_addr.return_value = ("10.10.10.10", 1111, "Full NAT")
        ccd = self.__get_config_desc()
        ts = TaskServer(Node(), ccd, EllipticalKeysAuth(self.path), self.client,
                        use_docker_machine_manager=False)
        self.ts = ts
        ts.task_manager.listen_port = 1111
        ts.task_manager.listen_address = "10.10.10.10"
        ts.receive_subtask_computation_time("xxyyzz", 1031)

        ctd = ComputeTaskDef()
        ctd.task_id = "xyz"
        ctd.subtask_id = "xxyyzz"
        ctd.environment = "DEFAULT"

        task_mock = self._get_task_manager_task_mock("xyz", "xxyyzz")
        task_mock.query_extra_data.return_value = ctd

        ts.task_manager.add_new_task(task_mock)
        ts.task_manager.tasks_states["xyz"].status = ts.task_manager.activeStatus[0]
        subtask = ts.task_manager.get_next_subtask("DEF", "DEF", "xyz",
                                                   1000, 10,  5, 10, 2,
                                                   "10.10.10.10")
        ts.receive_subtask_computation_time("xxyyzz", 1031)
        self.assertEqual(ts.task_manager.tasks_states["xyz"].subtask_states["xxyyzz"].computation_time, 1031)
        expected_value = ceil(1031 * 10 / 3600)
        assert ts.task_manager.tasks_states["xyz"].subtask_states["xxyyzz"].value == expected_value
        account_info = Mock()
        account_info.key_id = "key"
        prev_calls = ts.client.increase_trust.call_count
        ts.accept_result("xxyyzz", account_info)
        ts.client.transaction_system.add_payment_info.assert_called_with("xyz", "xxyyzz", expected_value, account_info)
        self.assertGreater(ts.client.increase_trust.call_count, prev_calls)

    @patch("golem.task.taskmanager.get_external_address")
    def test_results_no_payment_addr(self, mock_addr):
        mock_addr.return_value = ("10.10.10.10", 1111, "Full NAT")
        # FIXME: This test is too heavy, it starts up whole Golem Client.
        ccd = self.__get_config_desc()
        ts = TaskServer(Node(), ccd, EllipticalKeysAuth(self.path), self.client,
                        use_docker_machine_manager=False)
        ts.task_manager.listen_address = "10.10.10.10"
        ts.task_manager.listen_port = 1111
        ts.receive_subtask_computation_time("xxyyzz", 1031)

        self.ts = ts

        ctd = ComputeTaskDef()
        ctd.task_id = "xyz"
        ctd.subtask_id = "xxyyzz"
        ctd.environment = "DEFAULT"

        task_mock = self._get_task_manager_task_mock("xyz", "xxyyzz")
        task_mock.query_extra_data.return_value = ctd

        ts.task_manager.add_new_task(task_mock)
        ts.task_manager.tasks_states["xyz"].status = ts.task_manager.activeStatus[0]
        subtask = ts.task_manager.get_next_subtask("DEF", "DEF", "xyz", 1000, 10,  5, 10, 2, "10.10.10.10")

        ts.receive_subtask_computation_time("xxyyzz", 1031)
        account_info = Mock()
        account_info.key_id = "key"
        account_info.eth_account = Mock()
        account_info.eth_account.address = None

        ts.accept_result("xxyyzz", account_info)
        assert ts.client.transaction_system.add_payment_info.call_count == 0

    def test_traverse_nat(self):
        ccd = self.__get_config_desc()
        ts = TaskServer(Node(), ccd, EllipticalKeysAuth(self.path), self.client,
                        use_docker_machine_manager=False)
        self.ts = ts
        ts.network = Mock()
        ts.traverse_nat("ABC", "10.10.10.10", 1312, 310319041904, "DEF")
        self.assertEqual(ts.network.connect.call_args[0][0].socket_addresses[0].address,  "10.10.10.10")
        self.assertEqual(ts.network.connect.call_args[0][0].socket_addresses[0].port,  1312)

    def test_forwarded_session_requests(self):
        ccd = self.__get_config_desc()
        ts = TaskServer(Node(), ccd, EllipticalKeysAuth(self.path), self.client,
                        use_docker_machine_manager=False)
        self.ts = ts
        ts.network = Mock()

        key_id = str(uuid.uuid4())
        conn_id = str(uuid.uuid4())
        subtask_id = str(uuid.uuid4())

        ts.add_forwarded_session_request(key_id, conn_id)
        assert len(ts.forwarded_session_requests) == 1

        ts.forwarded_session_requests[key_id]['time'] = 0
        ts._sync_forwarded_session_requests()
        assert len(ts.forwarded_session_requests) == 0

        ts.add_forwarded_session_request(key_id, conn_id)
        ts.forwarded_session_requests[key_id] = None
        ts._sync_forwarded_session_requests()
        assert len(ts.forwarded_session_requests) == 0

        session = MagicMock()
        session.address = '127.0.0.1'
        session.port = 65535

        ts.conn_established_for_type[TaskConnTypes.TaskFailure](
            session, conn_id, key_id, subtask_id, "None"
        )
        assert ts.task_sessions[subtask_id] == session

    def test_retry_sending_task_result(self):
        ccd = self.__get_config_desc()
        ts = TaskServer(Node(), ccd, EllipticalKeysAuth(self.path), self.client,
                        use_docker_machine_manager=False)
        self.ts = ts
        ts.network = Mock()

        subtask_id = 'xxyyzz'
        wtr = Mock()
        wtr.already_sending = True

        ts.results_to_send[subtask_id] = wtr

        ts.retry_sending_task_result(subtask_id)
        assert not wtr.already_sending

    def test_send_waiting_results(self):
        ccd = self.__get_config_desc()
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
        assert not ts._add_pending_request.called

        wtr.last_sending_trial = 0
        ts.retry_sending_task_result(subtask_id)

        ts.sync_network()
        assert ts._add_pending_request.called

        ts._add_pending_request.called = False
        ts.task_sessions[subtask_id] = Mock()

        ts.sync_network()
        assert not ts._add_pending_request.called

        ts._add_pending_request.called = False
        ts.results_to_send = dict()

        wtf = wtr

        ts.failures_to_send[subtask_id] = wtf
        ts.sync_network()
        assert not ts._add_pending_request.called
        assert not ts.failures_to_send

        ts._add_pending_request.called = False
        ts.task_sessions.pop(subtask_id)

        ts.failures_to_send[subtask_id] = wtf
        ts.sync_network()
        assert ts._add_pending_request.called
        assert not ts.failures_to_send

    def test_add_task_session(self):
        ccd = self.__get_config_desc()
        ts = TaskServer(Node(), ccd, Mock(), self.client,
                        use_docker_machine_manager=False)
        self.ts = ts
        ts.network = Mock()

        session = Mock()
        subtask_id = 'xxyyzz'
        ts.add_task_session(subtask_id, session)
        assert ts.task_sessions[subtask_id]

    def test_initiate_nat_traversal(self):
        ccd = self.__get_config_desc()
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
        assert not ts._add_pending_request.called

        initiate(key_id, node_info, super_node_info, ans_conn_id)
        ts._add_pending_request.assert_called_with(TaskConnTypes.NatPunch,
                                                   ANY, ANY, ANY, ANY)

        node.nat_type = None
        initiate(key_id, node_info, super_node_info, ans_conn_id)
        ts._add_pending_request.assert_called_with(TaskConnTypes.Middleman,
                                                   ANY, ANY, ANY, ANY)

    def test_remove_task_session(self):
        ccd = self.__get_config_desc()
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
        ccd = self.__get_config_desc()
        ts = TaskServer(Node(), ccd, Mock(), self.client,
                        use_docker_machine_manager=False)
        self.ts = ts
        ts.network = Mock()
        session = Mock()

        ts.respond_to('key_id', session, 'conn_id')
        assert session.dropped.called

        session.dropped.called = False
        ts.response_list['conn_id'] = deque([lambda *_: lambda x: x])
        ts.respond_to('key_id', session, 'conn_id')
        assert not session.dropped.called

    def test_conn_for_task_failure_established(self):
        ccd = self.__get_config_desc()
        ts = TaskServer(Node(), ccd, Mock(), self.client,
                        use_docker_machine_manager=False)
        self.ts = ts
        ts.network = Mock()
        session = Mock()
        session.address = '127.0.0.1'
        session.port = 40102

        method = ts._TaskServer__connection_for_task_failure_established
        method(session, 'conn_id', 'key_id', 'subtask_id', 'err_msg')

        assert session.key_id == 'key_id'
        assert 'subtask_id' in ts.task_sessions
        assert session.send_hello.called
        session.send_task_failure.assert_called_once_with('subtask_id', 'err_msg')

    def test_conn_for_start_session_failure(self):

        ccd = self.__get_config_desc()
        ts = TaskServer(Node(), ccd, Mock(), self.client,
                        use_docker_machine_manager=False)
        self.ts = ts
        ts.network = Mock()
        ts.final_conn_failure = Mock()

        method = ts._TaskServer__connection_for_start_session_failure
        method('conn_id', 'key_id', Mock(), Mock(), 'ans_conn_id')

        ts.final_conn_failure.assert_called_with('conn_id')

    def test_conn_final_failures(self):

        ccd = self.__get_config_desc()
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

        assert ts.remove_pending_conn.called
        assert ts.remove_responses.called
        ts.remove_pending_conn.called = False
        ts.remove_responses.called = False

        method = ts._TaskServer__connection_for_task_result_final_failure
        wtr = Mock()
        method('conn_id', 'key_id', wtr)

        assert ts.remove_pending_conn.called
        assert ts.remove_responses.called
        assert not wtr.alreadySending
        assert wtr.lastSendingTrial

        ts.remove_pending_conn.called = False
        ts.remove_responses.called = False

        method = ts._TaskServer__connection_for_task_failure_final_failure
        method('conn_id', 'key_id', 'subtask_id', 'err_msg')

        assert ts.remove_pending_conn.called
        assert ts.remove_responses.called
        assert ts.task_computer.session_timeout.called
        ts.remove_pending_conn.called = False
        ts.remove_responses.called = False
        ts.task_computer.session_timeout.called = False

        method = ts._TaskServer__connection_for_start_session_final_failure
        method('conn_id', 'key_id', Mock(), Mock(), 'ans_conn_id')

        assert ts.remove_pending_conn.called
        assert ts.remove_responses.called
        assert ts.task_computer.session_timeout.called

    def __get_config_desc(self):
        ccd = ClientConfigDescriptor()
        ccd.root_path = self.path
        ccd.estimated_lux_performance = 2000.0
        ccd.estimated_blender_performance = 2000.0
        return ccd

    @staticmethod
    def __get_example_task_header():
        return {
            "task_id": "uvw",
            "node_name": "ABC",
            "environment": "DEFAULT",
            "task_owner": Node(),
            "task_owner_port": 10101,
            "task_owner_key_id": "key",
            "task_owner_address": "10.10.10.10",
            "deadline": timeout_to_deadline(1201),
            "subtask_timeout": 120,
            "max_price": 20,
            "resource_size": 2 * 1024,
            "estimated_memory": 3 * 1024,
            "signature": None
        }

    def _get_task_manager_task_mock(self, task_id, subtask_id):
        task_mock = Mock()
        task_mock.header = TaskHeader.from_dict(self.__get_example_task_header())
        task_mock.header.task_id = task_id
        task_mock.header.max_price = 10000

        ctd = ComputeTaskDef()
        ctd.task_id = task_id
        ctd.subtask_id = subtask_id

        task_mock.query_extra_data.return_value = ctd
        return task_mock
