# pylint: disable=protected-access, too-many-lines
import os
import random
import uuid
from collections import deque
from math import ceil
from unittest.mock import Mock, MagicMock, patch, ANY

from eth_utils import encode_hex
from golem_messages import idgenerator
from golem_messages import factories as msg_factories
from golem_messages import message
from requests import HTTPError

import golem
from golem import model
from golem import testutils
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.common import timeout_to_deadline, node_info_str
from golem.core.keysauth import KeysAuth
from golem.environments.environment import SupportStatus, UnsupportReason
from golem.network.hyperdrive.client import HyperdriveClientOptions, \
    HyperdriveClient, to_hyperg_peer
from golem.network.p2p.node import Node
from golem.resource.dirmanager import DirManager
from golem.resource.hyperdrive.resource import ResourceError
from golem.resource.hyperdrive.resourcesmanager import HyperdriveResourceManager
from golem.task import tasksession
from golem.task.masking import Mask
from golem.task.server import concent as server_concent
from golem.task.taskbase import TaskHeader, ResultType, AcceptClientVerdict
from golem.task.taskserver import TASK_CONN_TYPES
from golem.task.taskserver import TaskServer, WaitingTaskResult, logger
from golem.task.tasksession import TaskSession
from golem.task.taskstate import TaskState, TaskOp
from golem.tools.assertlogs import LogTestCase
from golem.tools.testwithreactor import TestDatabaseWithReactor
from golem.utils import pubkeytoaddr

from tests.factories.p2p import Node as NodeFactory
from tests.factories.resultpackage import ExtractedPackageFactory


def get_example_task_header(key_id):
    return {
        "fixed_header": {
            "task_id": idgenerator.generate_id(key_id),
            "environment": "DEFAULT",
            "task_owner": dict(
                key=encode_hex(key_id)[2:],
                node_name="ABC",
                prv_port=40103,
                prv_addr='10.0.0.10',
                pub_port=40103,
                pub_addr='1.2.3.4'
            ),
            "deadline": timeout_to_deadline(1201),
            "subtask_timeout": 120,
            "max_price": 20,
            "resource_size": 2 * 1024,
            "estimated_memory": 3 * 1024,
            "signature": None,
            "min_version": golem.__version__,
            "subtasks_count": 21,
            "concent_enabled": False,
        },
        "mask": {
            "byte_repr": Mask().to_bytes()
        },
        "timestamp": 0,
    }


def get_mock_task(key_gen="whatsoever", subtask_id="whatever"):
    task_mock = Mock()
    key_id = str.encode(key_gen)
    task_mock.header = TaskHeader.from_dict(get_example_task_header(key_id))
    task_id = task_mock.header.task_id
    task_mock.header.max_price = 1010
    task_mock.query_extra_data.return_value.ctd = message.tasks.ComputeTaskDef(
        task_id=task_id,
        subtask_id=subtask_id,
        task_type=message.tasks.TaskType.Blender.name,  # noqa pylint:disable=no-member
        meta_parameters=msg_factories.tasks.BlenderScriptPackageFactory(),
    )
    return task_mock


class TaskServerTestBase(LogTestCase,
                         testutils.DatabaseFixture,
                         testutils.TestWithClient):
    def setUp(self):
        super().setUp()
        random.seed()
        self.ccd = ClientConfigDescriptor()
        self.client.concent_service.enabled = False
        with patch(
                'golem.network.concent.handlers_library.HandlersLibrary'
                '.register_handler',):
            self.ts = TaskServer(
                node=NodeFactory(),
                config_desc=self.ccd,
                client=self.client,
                use_docker_manager=False,
            )

    def tearDown(self):
        LogTestCase.tearDown(self)
        testutils.DatabaseFixture.tearDown(self)

        if hasattr(self, "ts") and self.ts:
            self.ts.quit()


class TestTaskServer(TaskServerTestBase):  # noqa pylint: disable=too-many-public-methods
    @patch(
        'golem.network.concent.handlers_library.HandlersLibrary'
        '.register_handler',
    )
    @patch('golem.task.taskarchiver.TaskArchiver')
    def test_request(self, tar, *_):
        ccd = ClientConfigDescriptor()
        ccd.min_price = 10
        n = NodeFactory()
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

        keys_auth = KeysAuth(self.path, 'prv_key', '')
        task_header = get_example_task_header(keys_auth.public_key)
        task_id = task_header["fixed_header"]["task_id"]
        ts.add_task_header(task_header)
        self.assertEqual(ts.request_task(), task_id)
        assert ts.remove_task_header(task_id)

        task_header = get_example_task_header(keys_auth.public_key)
        task_header["fixed_header"]["task_owner"]["pub_port"] = 0
        task_id2 = task_header["fixed_header"]["task_id"]
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
        task_id3 = task_header["fixed_header"]["task_id"]
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
        task_id4 = task_header["fixed_header"]["task_id"]
        task_header["fixed_header"]["max_price"] = 1
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
        task_id5 = task_header["fixed_header"]["task_id"]
        ts.add_task_header(task_header)
        self.assertIsNone(ts.request_task())
        tar.add_support_status.assert_called_with(
            task_id5,
            SupportStatus(
                False,
                {UnsupportReason.DENY_LIST: keys_auth.key_id}))
        assert ts.remove_task_header(task_id5)

    @patch(
        "golem.task.taskserver.TaskServer.should_accept_requestor",
        return_value=SupportStatus(True),
    )
    def test_request_task_concent_required(self, *_):
        self.ts.client.concent_service.enabled = True
        self.ts.task_archiver = Mock()
        keys_auth = KeysAuth(self.path, 'prv_key', '')
        task_dict = get_example_task_header(keys_auth.public_key)
        task_dict['fixed_header']['concent_enabled'] = False
        self.ts.add_task_header(task_dict)

        self.assertIsNone(self.ts.request_task())
        self.ts.task_archiver.add_support_status.assert_called_once_with(
            task_dict['fixed_header']['task_id'],
            SupportStatus(
                False,
                {UnsupportReason.CONCENT_REQUIRED: True},
            ),
        )

    @patch("golem.task.taskserver.Trust")
    def test_send_results(self, trust, *_):
        ccd = ClientConfigDescriptor()
        ccd.min_price = 11
        keys_auth = KeysAuth(self.path, 'priv_key', '')
        task_header = get_example_task_header(keys_auth.public_key)
        n = Node.from_dict(task_header["fixed_header"]['task_owner'])

        ts = self.ts
        ts._is_address_accessible = Mock(return_value=True)
        ts.verify_header_sig = lambda x: True
        ts.client.get_suggested_addr.return_value = "10.10.10.10"
        ts.client.get_requesting_trust.return_value = ts.max_trust

        results = {"data": "", "result_type": ResultType.DATA}
        task_header = get_example_task_header(keys_auth.public_key)
        task_id = task_header["fixed_header"]["task_id"]
        assert ts.add_task_header(task_header)
        assert ts.request_task()
        subtask_id = idgenerator.generate_new_id_from_id(task_id)
        subtask_id2 = idgenerator.generate_new_id_from_id(task_id)
        self.assertTrue(ts.send_results(subtask_id, task_id, results))
        self.assertTrue(ts.send_results(subtask_id2, task_id, results))
        wtr = ts.results_to_send[subtask_id]
        self.assertIsInstance(wtr, WaitingTaskResult)
        self.assertEqual(wtr.subtask_id, subtask_id)
        self.assertEqual(wtr.result, "")
        self.assertEqual(wtr.result_type, ResultType.DATA)
        self.assertEqual(wtr.last_sending_trial, 0)
        self.assertEqual(wtr.delay_time, 0)
        self.assertEqual(wtr.owner, n)
        self.assertEqual(wtr.already_sending, False)

        self.assertIsNotNone(ts.task_keeper.task_headers.get(task_id))

        ctd = message.tasks.ComputeTaskDef(
            task_type=message.tasks.TaskType.Blender.name,  # noqa pylint:disable=no-member
            meta_parameters=msg_factories.tasks.BlenderScriptPackageFactory(),
        )
        ctd['task_id'] = task_id
        ctd['subtask_id'] = subtask_id
        ttc = msg_factories.tasks.TaskToComputeFactory(price=1)
        ttc.compute_task_def = ctd
        ts.task_manager.comp_task_keeper.receive_subtask(ttc)

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

        self.assertTrue(ts.add_task_header(task_header))
        self.assertEqual(len(ts.get_others_tasks_headers()), 1)

        task_header = get_example_task_header(keys_auth_2.public_key)
        task_id2 = task_header["fixed_header"]["task_id"]
        task_header["signature"] = keys_auth_2.sign(
            TaskHeader.dict_to_binary(task_header))

        self.assertTrue(ts.add_task_header(task_header))
        self.assertEqual(len(ts.get_others_tasks_headers()), 2)

        self.assertTrue(ts.add_task_header(task_header))
        self.assertEqual(len(ts.get_others_tasks_headers()), 2)

        new_header = dict(task_header)
        new_header["fixed_header"]["task_owner"]["pub_port"] = 9999
        new_header["signature"] = keys_auth_2.sign(
            TaskHeader.dict_to_binary(new_header))

        # An attempt to update fixed header should *not* succeed
        self.assertFalse(ts.add_task_header(new_header))
        self.assertEqual(len(ts.get_others_tasks_headers()), 2)
        saved_task = next(th for th in ts.get_others_tasks_headers()
                          if th["fixed_header"]["task_id"] == task_id2)
        self.assertEqual(saved_task["signature"], task_header["signature"])

    @patch("golem.task.taskserver.TaskServer._sync_pending")
    def test_sync(self, *_):
        self.ts.sync_network()
        self.ts._sync_pending.assert_called_once_with()

    @patch("golem.task.taskserver.TaskServer._sync_pending",
           side_effect=RuntimeError("Intentional failure"))
    @patch("golem.task.server.concent.process_messages_received_from_concent")
    def test_sync_job_fails(self, *_):
        self.ts.sync_network()
        # Other jobs should be called even in case of failure of previous ones
        # pylint: disable=no-member
        server_concent.process_messages_received_from_concent\
            .assert_called_once()
        # pylint: enable=no-member

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
        # given
        ts = self.ts

        task = get_mock_task()
        node_id = "0xdeadbeef"
        node_name = "deadbeef"
        task_id = task.header.task_id
        ts.task_manager.tasks[task_id] = task
        task.should_accept_client.return_value = AcceptClientVerdict.ACCEPTED

        min_accepted_perf = 77
        env = Mock()
        env.get_min_accepted_performance.return_value = min_accepted_perf
        ts.get_environment_by_id = Mock(return_value=env)
        node_name_id = node_info_str(node_name, node_id)
        ids = 'provider={}, task_id={}'.format(node_name_id, task_id)

        def _assert_log_msg(logger_mock, msg):
            self.assertEqual(len(logger_mock.output), 1)
            self.assertEqual(logger_mock.output[0].strip(), msg)

        # then
        with self.assertLogs(logger, level='INFO') as cm:
            assert not ts.should_accept_provider(
                node_id, node_name, 'tid', 27.18, 1, 1, 7)
            _assert_log_msg(
                cm,
                f'INFO:{logger.name}:Cannot find task in my tasks: '
                f'provider={node_name_id}, task_id=tid')

        with self.assertLogs(logger, level='INFO') as cm:
            assert not ts.should_accept_provider(
                node_id, node_name, task_id, 27.18, 1, 1, 7)
            _assert_log_msg(
                cm,
                f'INFO:{logger.name}:insufficient provider performance: '
                f'27.18 < {min_accepted_perf}; {ids}')

        with self.assertLogs(logger, level='INFO') as cm:
            assert not ts.should_accept_provider(
                node_id, node_name, task_id, 99, 1.72, 1, 4)
            _assert_log_msg(
                cm,
                f'INFO:{logger.name}:insufficient provider disk size:'
                f' 1.72 KiB; {ids}')

        with self.assertLogs(logger, level='INFO') as cm:
            assert not ts.should_accept_provider(
                node_id, node_name, task_id, 999, 3, 2.7, 1)
            _assert_log_msg(
                cm,
                f'INFO:{logger.name}:insufficient provider memory size:'
                f' 2.7 KiB; {ids}')

        # given
        self.client.get_computing_trust = Mock(return_value=0.4)
        ts.config_desc.computing_trust = 0.2
        # then
        assert ts.should_accept_provider(node_id, node_name, task_id, 99, 3, 4,
                                         5)

        # given
        ts.config_desc.computing_trust = 0.4
        # then
        assert ts.should_accept_provider(node_id, node_name, task_id, 99, 3, 4,
                                         5)

        # given
        ts.config_desc.computing_trust = 0.5
        # then
        with self.assertLogs(logger, level='INFO') as cm:
            assert not ts.should_accept_provider(node_id, node_name, task_id,
                                                 99, 3, 4, 5)
            _assert_log_msg(
                cm,
                f'INFO:{logger.name}:insufficient provider trust level:'
                f' 0.4; {ids}')

        # given
        ts.config_desc.computing_trust = 0.2
        # then
        assert ts.should_accept_provider(node_id, node_name, task_id, 99, 3, 4,
                                         5)

        task.header.mask = Mask(b'\xff' * Mask.MASK_BYTES)
        with self.assertLogs(logger, level='INFO') as cm:
            assert not ts.should_accept_provider(node_id, node_name, task_id,
                                                 99, 3, 4, 5)
            _assert_log_msg(
                cm,
                f'INFO:{logger.name}:network mask mismatch: {ids}')

        # given
        task.header.mask = Mask()
        task.should_accept_client.return_value = AcceptClientVerdict.REJECTED
        # then
        with self.assertLogs(logger, level='INFO') as cm:
            assert not ts.should_accept_provider(node_id, node_name, task_id,
                                                 99, 3, 4, 5)
            _assert_log_msg(
                cm,
                f'INFO:{logger.name}:provider {node_id}'
                f' is not allowed for this task at this moment '
                f'(either waiting for results or previously failed)'
            )

        # given
        task.header.mask = Mask()
        ts.acl.disallow(node_id)
        # then
        with self.assertLogs(logger, level='INFO') as cm:
            assert not ts.should_accept_provider(node_id, node_name, task_id,
                                                 99, 3, 4, 5)
            _assert_log_msg(
                cm,
                f'INFO:{logger.name}:provider node is blacklisted; {ids}')

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

    def test_download_options_errors(self, *_):
        built_options = Mock()
        rm = Mock(build_client_options=Mock(return_value=built_options))
        self.ts._get_resource_manager = Mock(return_value=rm)

        assert self.ts.get_download_options(
            received_options=None,
            task_id='task_id'
        ) is built_options

        assert self.ts.get_download_options(
            received_options={'options': {'peers': ['Invalid']}},
            task_id='task_id'
        ) is built_options

        assert self.ts.get_download_options(
            received_options=Mock(filtered=Mock(side_effect=Exception)),
            task_id='task_id'
        ) is built_options

    def test_pause_and_resume(self, *_):
        from apps.core.task.coretask import CoreTask

        assert self.ts.active
        assert not CoreTask.VERIFICATION_QUEUE._paused

        self.ts.pause()

        assert not self.ts.active
        assert CoreTask.VERIFICATION_QUEUE._paused

        self.ts.resume()

        assert self.ts.active
        assert not CoreTask.VERIFICATION_QUEUE._paused


class TestTaskServer2(TestDatabaseWithReactor, testutils.TestWithClient):
    def setUp(self):
        for parent in self.__class__.__bases__:
            parent.setUp(self)
        random.seed()
        self.ccd = self._get_config_desc()
        with patch('golem.network.concent.handlers_library.HandlersLibrary'
                   '.register_handler',):
            self.ts = TaskServer(
                node=NodeFactory(),
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
        task_id = str(uuid.uuid4())
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
    def test_results(self, trust, *_):
        ts = self.ts
        ts.task_manager.listen_port = 1111
        ts.task_manager.listen_address = "10.10.10.10"

        task_mock = get_mock_task("xyz", "xxyyzz")
        task_mock.get_trust_mod.return_value = ts.max_trust
        task_id = task_mock.header.task_id
        extra_data = Mock()
        extra_data.ctd = message.tasks.ComputeTaskDef(
            task_type=message.tasks.TaskType.Blender.name,  # noqa pylint:disable=no-member
            meta_parameters=msg_factories.tasks.BlenderScriptPackageFactory(),
        )
        extra_data.ctd['task_id'] = task_mock.header.task_id
        extra_data.ctd['subtask_id'] = "xxyyzz"
        task_mock.query_extra_data.return_value = extra_data
        task_mock.task_definition.subtask_timeout = 3600
        task_mock.should_accept_client.return_value = \
            AcceptClientVerdict.ACCEPTED

        ts.task_manager.add_new_task(task_mock)
        ts.task_manager.tasks_states[task_id].status = \
            ts.task_manager.activeStatus[0]
        subtask = ts.task_manager.get_next_subtask(
            "DEF",
            "DEF",
            task_id,
            1000, 10,
            5, 10, 2,
            "10.10.10.10")
        assert subtask is not None
        expected_value = ceil(1031 * 1010 / 3600)
        ts.task_manager.set_subtask_value("xxyyzz", expected_value)
        prev_calls = trust.COMPUTED.increase.call_count
        ts.accept_result("xxyyzz", "key", "eth_address")
        ts.client.transaction_system.add_payment_info.assert_called_with(
            "xxyyzz",
            expected_value,
            "eth_address")
        self.assertGreater(trust.COMPUTED.increase.call_count, prev_calls)

    @patch("golem.task.taskmanager.TaskManager.dump_task")
    @patch("golem.task.taskserver.Trust")
    def test_results_no_payment_addr(self, *_):
        # FIXME: This test is too heavy, it starts up whole Golem Client.
        ts = self.ts
        ts.task_manager.listen_address = "10.10.10.10"
        ts.task_manager.listen_port = 1111

        extra_data = Mock()
        extra_data.ctd = message.tasks.ComputeTaskDef(
            task_type=message.tasks.TaskType.Blender.name,  # noqa pylint:disable=no-member
            meta_parameters=msg_factories.tasks.BlenderScriptPackageFactory()
        )
        extra_data.ctd['subtask_id'] = "xxyyzz"

        task_mock = get_mock_task("xyz", "xxyyzz")
        task_id = task_mock.header.task_id
        task_mock.get_trust_mod.return_value = ts.max_trust
        extra_data.ctd['task_id'] = task_id
        task_mock.query_extra_data.return_value = extra_data
        task_mock.task_definition.subtask_timeout = 3600
        task_mock.should_accept_client.return_value = \
            AcceptClientVerdict.ACCEPTED

        ts.task_manager.add_new_task(task_mock)
        ts.task_manager.tasks_states[task_id].status = \
            ts.task_manager.activeStatus[0]
        subtask = ts.task_manager.get_next_subtask(
            "DEF", "DEF", task_id, 1000, 10, 5, 10, 2, "10.10.10.10")

        assert subtask is not None
        ts.accept_result("xxyyzz", "key", "eth_address")
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

        self.node = Mock(prv_addr='10.0.0.2', prv_port=40102,
                         pub_addr='1.2.3.4', pub_port=40102,
                         hyperg_prv_port=3282, hyperg_pub_port=3282,
                         prv_addresses=['10.0.0.2'],)

        self.resource_manager = Mock(
            add_task=Mock(side_effect=lambda *a, **b: ([], "a1b2c3"))
        )
        with patch('golem.network.concent.handlers_library.HandlersLibrary'
                   '.register_handler',):
            self.ts = TaskServer(
                node=self.node,
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
            task.header.deadline = 2524608000
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

    def test_restore_resources_call(self, *_):
        self._create_tasks(self.ts, 1)

        task_states = self.ts.task_manager.tasks_states
        task_id = next(iter(task_states.keys()))
        task_state = next(iter(task_states.values()))
        task_state.package_path = os.path.join(self.path, task_id + '.bin')
        task_state.resource_hash = str(uuid.uuid4())

        self.ts._restore_resources = Mock()
        self.ts.restore_resources()

        self.ts._restore_resources.assert_called_with(
            [task_state.package_path], task_id,
            resource_hash=task_state.resource_hash, timeout=ANY
        )

    def test_finished_task_listener(self, *_):
        self.ts.client = Mock()
        remove_task = self.ts.client.p2pservice.remove_task
        remove_task_funds_lock = self.ts.client.funds_locker.remove_task

        values = dict(TaskOp.__members__)
        values.pop('FINISHED')
        values.pop('TIMEOUT')

        for value in values:
            self.ts.finished_task_listener(op=value)
            assert not remove_task.called

        for value in values:
            self.ts.finished_task_listener(event='task_status_updated',
                                           op=value)
            assert not remove_task.called

        self.ts.finished_task_listener(event='task_status_updated',
                                       op=TaskOp.FINISHED)
        assert remove_task.called
        assert remove_task_funds_lock.called

        self.ts.finished_task_listener(event='task_status_updated',
                                       op=TaskOp.TIMEOUT)
        assert remove_task.call_count == 2
        assert remove_task_funds_lock.call_count == 2


class TaskVerificationResultTest(TaskServerTestBase):

    def setUp(self):
        super().setUp()
        self.conn_id = 'connid'
        self.key_id = 'keyid'
        self.conn_type = TASK_CONN_TYPES['task_verification_result']

    @staticmethod
    def _mock_session():
        session = Mock()
        session.address = "10.10.10.10"
        session.port = 1020
        return session

    def test_connection_established(self):
        session = self._mock_session()
        extracted_package = ExtractedPackageFactory()
        subtask_id = extracted_package.descriptor.subtask_id

        self.ts.conn_established_for_type[self.conn_type](
            session, self.conn_id, extracted_package, self.key_id
        )
        self.assertEqual(session.task_id, subtask_id)
        self.assertEqual(session.key_id, self.key_id)
        self.assertEqual(session.conn_id, self.conn_id)
        self.assertEqual(self.ts.task_sessions[subtask_id], session)
        result_received_call = session.result_received.call_args[0]
        self.assertEqual(result_received_call[0].get('subtask_id'), subtask_id)

    @patch('golem.task.taskserver.logger.warning')
    def test_conection_failed(self, log_mock):
        extracted_package = ExtractedPackageFactory()
        subtask_id = extracted_package.descriptor.subtask_id
        self.ts.conn_failure_for_type[self.conn_type](
            self.conn_id, extracted_package, self.key_id
        )
        self.assertIn(
            "Failed to establish a session", log_mock.call_args[0][0])
        self.assertIn(subtask_id, log_mock.call_args[0][1])
        self.assertIn(self.key_id, log_mock.call_args[0][2])

    @patch('golem.task.taskserver.TaskServer._is_address_accessible',
           Mock(return_value=True))
    @patch('golem.task.taskserver.TaskServer.get_socket_addresses',
           Mock(return_value=[Mock()]))
    def test_verify_results(self, *_):
        rct = msg_factories.tasks.ReportComputedTaskFactory(
            node_info=self.ts.node.to_dict())
        extracted_package = ExtractedPackageFactory()
        self.ts.verify_results(rct, extracted_package)
        pc = list(self.ts.pending_connections.values())[0]

        self.assertEqual(
            pc.established.func.__name__,
            '__connection_for_task_verification_result_established')
        self.assertEqual(
            pc.failure.func.__name__,
            '__connection_for_task_verification_result_failure',
        )
        self.assertEqual(
            pc.final_failure.func.__name__,
            '__connection_for_task_verification_result_failure',
        )
