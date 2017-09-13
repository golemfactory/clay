import datetime
import os
import random
import uuid
from math import ceil

from mock import Mock, MagicMock, patch, ANY

from golem import model
from golem import testutils
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.common import timeout_to_deadline
from golem.core.keysauth import EllipticalKeysAuth
from golem.core.variables import APP_VERSION
from golem.network.p2p.node import Node
from golem.task.taskbase import ComputeTaskDef, TaskHeader, ResultType
from golem.task.taskserver import TaskServer, WaitingTaskResult, logger
from golem.tools.assertlogs import LogTestCase
from golem.tools.testwithappconfig import TestWithKeysAuth
from golem.tools.testwithreactor import TestDirFixtureWithReactor


def get_example_task_header():
    return {
        "task_id": "uvw",
        "node_name": "ABC",
        "environment": "DEFAULT",
        "task_owner": dict(key=b'1' * 32),
        "task_owner_port": 10101,
        "task_owner_key_id": b'1' * 32,
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
    task_mock.header.max_price = 1010
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
                             self.client, Mock(),
                             use_docker_machine_manager=False)

    def tearDown(self):
        LogTestCase.tearDown(self)
        TestWithKeysAuth.tearDown(self)

        if hasattr(self, "ts") and self.ts:
            self.ts.quit()

    def test_request(self):
        ccd = self._get_config_desc()
        ccd.min_price = 10
        n = Node()
        n.prv_addresses = []
        ka = EllipticalKeysAuth(self.path)
        ts = TaskServer(n, ccd, ka, self.client, Mock(),
                        use_docker_machine_manager=False)
        ts.verify_header_sig = lambda x: True
        self.ts = ts
        ts.client.get_suggested_addr.return_value = "10.10.10.10"
        ts.client.get_requesting_trust.return_value = 0.3
        self.assertIsInstance(ts, TaskServer)
        self.assertIsNone(ts.request_task())
        n2 = Node()
        n2.prv_addresses = []
        n2.prv_addr = "10.10.10.10"
        n2.port = 10101
        task_header = get_example_task_header()
        task_header["task_owner"] = n2
        ts.add_task_header(task_header)
        nr = ts.request_task()
        self.assertEqual(nr, "uvw")
        ts.remove_task_header("uvw")
        task_header["task_owner_port"] = 0
        task_header["task_id"] = "uvw2"
        self.assertTrue(ts.add_task_header(task_header))
        self.assertIsNotNone(ts.task_keeper.task_headers["uvw2"])

        # Requests are fully asynchronous now,
        # there IS a connection request pending
        self.assertIsNotNone(ts.request_task())
        self.assertIsNotNone(ts.task_keeper.task_headers.get("uvw2"))

    @patch('golem.task.taskserver.async_run')
    @patch("golem.task.taskserver.Trust")
    def test_send_result(self, trust, async_run):
        ccd = self._get_config_desc()
        ccd.min_price = 11
        n = Node()
        n.key = "key"
        n.prv_addresses = []
        ka = EllipticalKeysAuth(self.path)
        ts = TaskServer(n, ccd, ka, self.client, Mock(),
                        use_docker_machine_manager=False)
        ts.verify_header_sig = lambda x: True
        self.ts = ts

        ts.client.get_suggested_addr.return_value = "10.10.10.10"
        ts.client.get_requesting_trust.return_value = ts.max_trust
        results = {"data": "", "result_type": ResultType.DATA}
        task_header = get_example_task_header()
        task_header["task_id"] = "xyz"

        assert ts.add_task_header(task_header)
        assert ts.request_task()

        incomes_keeper = ts.client.transaction_system.incomes_keeper

        self.assertFalse(async_run.called)
        self.assertTrue(ts.send_result("xxyyzz", "xyz", 40, results, n))
        self.assertTrue(async_run.called)

        incomes_keeper.expect.reset_mock()
        async_run.reset_mock()

        self.assertFalse(async_run.called)
        self.assertTrue(ts.send_result("xyzxyz", "xyz", 40, results, n))

        self.assertEqual(ts.get_subtask_ttl("xyz"), 120)
        incomes_keeper.expect.assert_called_once_with(
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

    def test_change_config(self):
        ccd = self._get_config_desc()
        ccd.task_session_timeout = 40
        ccd.min_price = 1.0
        ccd.task_request_interval = 10
        # ccd.use_waiting_ttl = True
        ccd.waiting_for_task_timeout = 19

        ts = TaskServer(Node(), ccd, EllipticalKeysAuth(self.path), self.client,
                        task_service=Mock(),
                        use_docker_machine_manager=False)
        self.ts = ts

        ccd2 = self._get_config_desc()
        ccd2.task_session_timeout = 124
        ccd2.min_price = 0.0057
        ccd2.task_request_interval = 31
        # ccd2.use_waiting_ttl = False
        ccd2.waiting_for_task_timeout = 90
        ts.change_config(ccd2)
        self.assertEqual(ts.config_desc, ccd2)
        self.assertEqual(ts.last_message_time_threshold, 124)
        self.assertEqual(ts.task_keeper.min_price, 0.0057)
        self.assertEqual(ts.task_computer.task_request_frequency, 31)
        self.assertEqual(ts.task_computer.waiting_for_task_timeout, 90)
        # self.assertEqual(ts.task_computer.use_waiting_ttl, False)

    def test_add_task_header(self):
        config = self._get_config_desc()
        keys_auth = EllipticalKeysAuth(self.path)
        keys_auth_2 = EllipticalKeysAuth(os.path.join(self.path, "2"))

        self.ts = ts = TaskServer(Node(), config, keys_auth, self.client,
                                  task_service=Mock(),
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
        saved_task = next(th for th in ts.get_tasks_headers() if th.task_id == "xyz_2")
        self.assertEqual(saved_task.signature, new_header["signature"])

    def test_sync(self):
        ccd = self._get_config_desc()
        ts = TaskServer(Node(), ccd, EllipticalKeysAuth(self.path), self.client,
                        Mock(),
                        use_docker_machine_manager=False)
        self.ts = ts
        ts.sync_network()

    def test_retry_sending_task_result(self):
        ccd = self._get_config_desc()
        ts = TaskServer(Node(), ccd, EllipticalKeysAuth(self.path), self.client,
                        Mock(),
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
        ts = TaskServer(Node(), ccd, Mock(), self.client, Mock(),
                        use_docker_machine_manager=False)
        self.ts = ts
        ts.network = Mock()
        ts._mark_connected = Mock()
        ts.task_computer = Mock()
        ts.task_manager = Mock()
        ts.task_manager.check_timeouts.return_value = []
        ts.task_keeper = Mock()
        ts.task_connections_helper = Mock()

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

        wtr.last_sending_trial = 0
        ts.retry_sending_task_result(subtask_id)

        ts.sync_network()
        ts.task_sessions[subtask_id] = Mock()
        ts.task_sessions[subtask_id].last_message_time = float('infinity')

        ts.sync_network()
        ts.results_to_send = dict()

        wtf = wtr

        ts.failures_to_send[subtask_id] = wtf
        ts.sync_network()
        self.assertEqual(ts.failures_to_send, {})

        ts.task_sessions.pop(subtask_id)

        ts.failures_to_send[subtask_id] = wtf
        ts.sync_network()
        self.assertEqual(ts.failures_to_send, {})

    def test_add_task_session(self):
        ccd = self._get_config_desc()
        ts = TaskServer(Node(), ccd, Mock(), self.client, Mock(),
                        use_docker_machine_manager=False)
        self.ts = ts
        ts.network = Mock()

        session = Mock()
        subtask_id = 'xxyyzz'
        ts.add_task_session(subtask_id, session)
        self.assertIsNotNone(ts.task_sessions[subtask_id])

    def test_remove_task_session(self):
        ccd = self._get_config_desc()
        ts = TaskServer(Node(), ccd, Mock(), self.client, Mock(),
                        use_docker_machine_manager=False)
        self.ts = ts
        ts.network = Mock()

        conn_id = str(uuid.uuid4())
        session = Mock()
        session.conn_id = conn_id

        ts.remove_task_session(session)
        ts.task_sessions['task'] = session
        ts.remove_task_session(session)

    def _get_config_desc(self):
        ccd = ClientConfigDescriptor()
        ccd.root_path = self.path
        ccd.estimated_lux_performance = 2000.0
        ccd.estimated_blender_performance = 2000.0
        ccd.estimated_dummytask_performance = 2000.0
        return ccd

    def test_should_accept_provider(self):
        ccd = self._get_config_desc()
        ts = TaskServer(Node(), ccd, Mock(), self.client, Mock(),
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
        ts = TaskServer(Node(), ccd, Mock(), self.client, Mock(),
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


class TestTaskServer2(TestWithKeysAuth, TestDirFixtureWithReactor):

    def setUp(self):
        for parent in self.__class__.__bases__:
            parent.setUp(self)
        random.seed()
        self.ccd = self._get_config_desc()
        self.ts = TaskServer(Node(), self.ccd, EllipticalKeysAuth(self.path),
                             self.client, Mock(),
                             use_docker_machine_manager=False)
        self.ts.task_computer = MagicMock()

    def tearDown(self):
        for parent in self.__class__.__bases__:
            parent.tearDown(self)

    @patch("golem.task.taskserver.TaskServer._find_sessions")
    def test_send_waiting(self, find_sessions_mock):
        session_cbk = MagicMock()
        node = Mock()
        elem = MagicMock()
        elem.subtask = 's' + str(uuid.uuid4())
        elem.get_sender_node.return_value = node
        elems_set = {elem}
        kwargs = {
            'elems_set': elems_set,
            'cb': session_cbk,
        }

        elem._last_try = datetime.datetime.now()
        self.ts._send_waiting_payments(**kwargs)
        find_sessions_mock.assert_not_called()

        find_sessions_mock.return_value = []
        elem._last_try = datetime.datetime.min
        self.ts._send_waiting_payments(**kwargs)
        find_sessions_mock.assert_called_once_with(elem.subtask)
        find_sessions_mock.reset_mock()

        self.ts.task_service.spawn_connect.assert_called_once_with(
            node.key,
            addresses=elem.get_sender_node().get_addresses(),
            cb=ANY,
            eb=ANY
        )
        self.ts.task_service.spawn_connect.reset_mock()

        # Test ordinary session
        session = Mock()
        find_sessions_mock.return_value = session
        elem._last_try = datetime.datetime.min
        self.ts._send_waiting_payments(**kwargs)
        find_sessions_mock.assert_called_once_with(elem.subtask)
        find_sessions_mock.reset_mock()
        session_cbk.assert_called_once_with(session, elem)
        session_cbk.reset_mock()

    @patch("golem.task.taskmanager.TaskManager.dump_task")
    @patch("golem.task.taskserver.Trust")
    def test_results(self, trust, dump_mock):
        ccd = self._get_config_desc()
        ts = TaskServer(Node(), ccd, EllipticalKeysAuth(self.path), self.client,
                        Mock(),
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
        task_mock.get_trust_mod.return_value = ts.max_trust
        task_mock.query_extra_data.return_value = extra_data

        ts.task_manager.add_new_task(task_mock)
        ts.task_manager.tasks_states["xyz"].status = ts.task_manager.activeStatus[0]
        subtask, wrong_task, wait = ts.task_manager.get_next_subtask("DEF", "DEF", "xyz",
                                                                     1000, 10, 5, 10, 2,
                                                                     "10.10.10.10")
        ts.receive_subtask_computation_time("xxyyzz", 1031)
        self.assertEqual(ts.task_manager.tasks_states["xyz"].subtask_states["xxyyzz"].computation_time, 1031)
        expected_value = ceil(1031 * 1010 / 3600)
        self.assertEqual(ts.task_manager.tasks_states["xyz"].subtask_states["xxyyzz"].value, expected_value)
        account_info = Mock()
        account_info.key_id = "key"
        prev_calls = trust.COMPUTED.increase.call_count
        ts.accept_result("xxyyzz", account_info)
        ts.client.transaction_system.add_payment_info.assert_called_with("xyz", "xxyyzz", expected_value, account_info)
        self.assertGreater(trust.COMPUTED.increase.call_count, prev_calls)

    @patch("golem.task.taskmanager.TaskManager.dump_task")
    @patch("golem.task.taskserver.Trust")
    def test_results_no_payment_addr(self, *_):
        # FIXME: This test is too heavy, it starts up whole Golem Client.
        ccd = self._get_config_desc()
        ts = TaskServer(Node(), ccd, EllipticalKeysAuth(self.path), self.client,
                        Mock(),
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
        task_mock.get_trust_mod.return_value = ts.max_trust
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
