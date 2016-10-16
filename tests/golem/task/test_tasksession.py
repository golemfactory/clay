import cPickle
import unittest

from mock import Mock, MagicMock, patch

from golem.core.keysauth import KeysAuth
from golem.network.p2p.node import Node
from golem.network.transport.message import (MessageWantToComputeTask, MessageCannotAssignTask, MessageTaskToCompute,
                                             MessageReportComputedTask, MessageHello,
                                             MessageSubtaskResultRejected, MessageSubtaskResultAccepted,
                                             MessageTaskResultHash, MessageGetTaskResult, MessageCannotComputeTask,
                                             MessageWaitingForResults, MessageContestWinner, MessageContestWinnerAccept,
                                             MessageContestWinnerReject)
from golem.task.taskbase import ComputeTaskDef, result_types
from golem.task.taskserver import WaitingTaskResult
from golem.task.tasksession import TaskSession, logger, TASK_PROTOCOL_ID
from golem.testutils import TempDirFixture
from golem.tools.assertlogs import LogTestCase


def Instance(cls):
    class _Instance(cls):
        def __eq__(self, other):
            return isinstance(other, cls)
    return _Instance()


class TestTaskSession(LogTestCase, TempDirFixture):
    def test_init(self):
        ts = TaskSession(Mock())
        self.assertIsInstance(ts, TaskSession)

    def test_encrypt(self):
        ts = TaskSession(Mock())
        data = "ABC"

        ts.key_id = "123"
        res = ts.encrypt(data)
        ts.task_server.encrypt.assert_called_with(data, "123")

        ts.task_server = None
        with self.assertLogs(logger, level=1):
            self.assertEqual(ts.encrypt(data), data)

    def test_decrypt(self):
        ts = TaskSession(Mock())
        data = "ABC"

        res = ts.decrypt(data)
        ts.task_server.decrypt.assert_called_with(data)
        self.assertIsNotNone(res)

        ts.task_server.decrypt = Mock(side_effect=AssertionError("Encrypt error"))
        with self.assertLogs(logger, level=1) as l:
            res = ts.decrypt(data)
        self.assertTrue(any("maybe it's not encrypted?" in log for log in l.output))
        self.assertFalse(any("Encrypt error" in log for log in l.output))
        self.assertEqual(res, data)

        ts.task_server.decrypt = Mock(side_effect=ValueError("Different error"))
        with self.assertLogs(logger, level=1) as l:
            res = ts.decrypt(data)
        self.assertTrue(any("Different error" in log for log in l.output))
        self.assertIsNone(res)

        ts.task_server = None
        data = "ABC"
        with self.assertLogs(logger, level=1):
            self.assertEqual(ts.encrypt(data), data)

    def test_request_task(self):
        ts = TaskSession(Mock())
        ts.verified = True
        ts.request_task("ABC", "xyz", 1030, 30, 3, 1, 8)
        mt = ts.conn.send_message.call_args[0][0]
        self.assertIsInstance(mt, MessageWantToComputeTask)
        self.assertEqual(mt.node_name, "ABC")
        self.assertEqual(mt.task_id, "xyz")
        self.assertEqual(mt.perf_index, 1030)
        self.assertEqual(mt.price, 30)
        self.assertEqual(mt.max_resource_size, 3)
        self.assertEqual(mt.max_memory_size, 1)
        self.assertEqual(mt.num_cores, 8)
        ts2 = TaskSession(Mock())
        ts2.verified = True
        ts2.key_id = "DEF"
        ts2.can_be_not_encrypted.append(mt.Type)
        ts2.can_be_unsigned.append(mt.Type)
        ts2.task_server.get_computing_trust.return_value = 0.1
        ts2.task_server.config_desc.computing_trust = 0.2
        ts2.task_server.config_desc.max_price = 100
        ts2.task_manager.get_next_subtask.return_value = ComputeTaskDef()
        ts2.task_manager.is_finishing.return_value = False
        ts2.interpret(mt)
        ts2.task_server.get_computing_trust.assert_called_with("DEF")
        ms = ts2.conn.send_message.call_args[0][0]
        self.assertIsInstance(ms, MessageCannotAssignTask)
        self.assertEqual(ms.task_id, mt.task_id)
        ts2.conn.send_message.call_args = []
        ts2.task_server.get_computing_trust.return_value = 0.8
        ts2.interpret(mt)
        assert not ts2.conn.send_message.call_args

    def test_send_report_computed_task(self):
        ts = TaskSession(Mock())
        ts.verified = True
        ts.task_server.get_node_name.return_value = "ABC"
        n = Node()
        wtr = WaitingTaskResult("xyz", "xxyyzz", "result", result_types["data"], 13190, 10, 0, "10.10.10.10",
                                30102, "key1", n)

        ts.send_report_computed_task(wtr, "10.10.10.10", 30102, "0x00", n)
        ms = ts.conn.send_message.call_args[0][0]
        self.assertIsInstance(ms, MessageReportComputedTask)
        self.assertEqual(ms.subtask_id, "xxyyzz")
        self.assertEqual(ms.result_type, 0)
        self.assertEqual(ms.computation_time, 13190)
        self.assertEqual(ms.node_name, "ABC")
        self.assertEqual(ms.address, "10.10.10.10")
        self.assertEqual(ms.port, 30102)
        self.assertEqual(ms.eth_account, "0x00")
        self.assertEqual(ms.extra_data, [])
        self.assertEqual(ms.node_info, n)
        ts2 = TaskSession(Mock())
        ts2.verified = True
        ts2.key_id = "DEF"
        ts2.can_be_not_encrypted.append(ms.Type)
        ts2.can_be_unsigned.append(ms.Type)
        ts2.task_manager.subtask2task_mapping = {"xxyyzz": "xyz"}
        ts2.interpret(ms)
        ts2.task_server.receive_subtask_computation_time.assert_called_with("xxyyzz", 13190)

    def test_react_to_hello(self):
        conn = MagicMock()

        node = Node(node_name='node', key='ffffffff')
        keys_auth = KeysAuth(self.path)
        keys_auth.key = node.key
        keys_auth.key_id = node.key

        ts = TaskSession(conn)
        ts.task_server = Mock()
        ts.disconnect = Mock()
        ts.send = Mock()

        def create_verify(value):
            def verify(*args):
                return value
            return verify

        key_id = 'deadbeef'
        peer_info = MagicMock()
        peer_info.key = key_id
        msg = MessageHello(port=1, node_name='node2', client_key_id=key_id, node_info=peer_info,
                           proto_id=-1)

        ts.verify = create_verify(False)
        ts._react_to_hello(msg)
        ts.disconnect.assert_called_with(TaskSession.DCRUnverified)

        ts.verify = create_verify(True)
        ts._react_to_hello(msg)
        ts.disconnect.assert_called_with(TaskSession.DCRProtocolVersion)

        msg.proto_id = TASK_PROTOCOL_ID

        ts._react_to_hello(msg)
        assert ts.send.called

    def test_result_received(self):
        conn = Mock()
        ts = TaskSession(conn)
        ts.task_server = Mock()
        ts.task_manager = Mock()
        ts.task_manager.verify_subtask.return_value = True

        extra_data = dict(
            # the result is explicitly serialized using cPickle
            result=cPickle.dumps({'stdout': 'xyz'}),
            result_type=None,
            subtask_id='xxyyzz'
        )

        ts.result_received(extra_data, decrypt=False)

        assert ts.msgs_to_send
        assert ts.msgs_to_send[0].__class__ == MessageSubtaskResultRejected
        assert conn.close.called

        extra_data.update(dict(
            result_type=result_types['data'],
        ))
        conn.close.called = False
        ts.msgs_to_send = []

        ts.result_received(extra_data, decrypt=False)

        assert ts.msgs_to_send
        assert ts.msgs_to_send[0].__class__ == MessageSubtaskResultAccepted
        assert conn.close.called

        extra_data.update(dict(
            subtask_id=None,
        ))
        conn.close.called = False
        ts.msgs_to_send = []

        ts.result_received(extra_data, decrypt=False)

        assert not ts.msgs_to_send
        assert conn.close.called

    def test_react_to_task_result_hash(self):

        def create_pull_package(result):
            def pull_package(multihash, task_id, subtask_id,
                             secret, success, error, *args, **kwargs):
                if result:
                    success(Mock())
                else:
                    error(Exception('Pull failed'))
            return pull_package

        conn = Mock()
        ts = TaskSession(conn)
        ts.result_received = Mock()
        ts.task_manager.subtask2task_mapping = dict()

        subtask_id = 'xxyyzz'
        secret = 'pass'
        multihash = 'multihash'

        ts.task_manager.subtask2task_mapping[subtask_id] = 'xyz'

        msg = MessageTaskResultHash(subtask_id=subtask_id, secret=secret, multihash=multihash,
                                    options=Mock())

        ts.task_manager.task_result_manager.pull_package = create_pull_package(True)
        ts._react_to_task_result_hash(msg)
        assert ts.result_received.called

        ts.task_manager.task_result_manager.pull_package = create_pull_package(False)
        ts._react_to_task_result_hash(msg)
        assert ts.task_server.reject_result.called
        assert ts.task_manager.task_computation_failure.called

    def test_react_to_task_compute(self):
        conn = Mock()
        ts = TaskSession(conn)
        ts.key_id = "KEY_ID"
        ts.task_manager = Mock()
        ts.task_computer = Mock()
        ts.task_server = Mock()
        ts.task_server.get_subtask_ttl.return_value = 31313

        def __reset_mocks():
            ts.task_manager.reset_mock()
            ts.task_computer.reset_mock()
            conn.reset_mock()

        msg = MessageTaskToCompute()
        with self.assertLogs(logger, level="WARNING"):
            ts._react_to_task_to_compute(msg)
        ts.task_manager.comp_task_keeper.receive_subtask.assert_not_called()
        ts.task_computer.session_closed.assert_called_with()
        assert conn.close.called

        __reset_mocks()
        ctd = ComputeTaskDef()
        ctd.key_id = "KEY_ID"
        ctd.subtask_id = "SUBTASKID"
        ctd.task_owner = Node()
        ctd.task_owner.key = "KEY_ID"
        ctd.return_address = "10.10.10.10"
        ctd.return_port = 1112
        msg = MessageTaskToCompute(ctd)
        ts._react_to_task_to_compute(msg)
        ts.task_manager.comp_task_keeper.receive_subtask.assert_called_with(ctd)
        ts.task_computer.session_closed.assert_not_called()
        ts.task_server.add_task_session.assert_called_with("SUBTASKID", ts)
        ts.task_computer.task_given.assert_called_with(ctd)
        conn.close.assert_not_called()

        __reset_mocks()
        ctd.key_id = "KEY_ID2"
        ts._react_to_task_to_compute(MessageTaskToCompute(ctd))
        ts.task_manager.comp_task_keeper.receive_subtask.assert_not_called()
        ts.task_computer.session_closed.assert_called_with()
        assert conn.close.called

        __reset_mocks()
        ctd.key_id = "KEY_ID"
        ctd.task_owner.key = "KEY_ID2"
        ts._react_to_task_to_compute(MessageTaskToCompute(ctd))
        ts.task_manager.comp_task_keeper.receive_subtask.assert_not_called()
        ts.task_computer.session_closed.assert_called_with()
        assert conn.close.called

        __reset_mocks()
        ctd.task_owner.key = "KEY_ID"
        ctd.return_port = 0
        ts._react_to_task_to_compute(MessageTaskToCompute(ctd))
        ts.task_manager.comp_task_keeper.receive_subtask.assert_not_called()
        ts.task_computer.session_closed.assert_called_with()
        assert conn.close.called

        __reset_mocks()
        ctd.task_owner.key = "KEY_ID"
        ctd.return_port = 1319
        ts._react_to_task_to_compute(MessageTaskToCompute(ctd))
        conn.close.assert_not_called()

    def test_react_to_want_to_compute_task(self):

        ts = self.__create_task_session()
        msg = MessageWantToComputeTask()

        def __reset(has_task=True, has_subtasks=True, is_finishing=False, trust_value=1.):
            tm = ts.task_manager
            tm.has_task.return_value = has_task
            tm.has_subtasks.return_value = has_subtasks
            tm.is_finishing.return_value = is_finishing
            tm.contest_manager.add_contender.called = False

            tsrv = ts.task_server
            tsrv.config_desc.computing_trust = 0.5
            tsrv.get_computing_trust.return_value = trust_value

            ts.send.called = False
            ts.send.call_args = None
            ts.dropped.called = False

        __reset(has_task=False)

        ts._react_to_want_to_compute_task(msg)
        assert ts.send.called
        assert isinstance(ts.send.call_args[0][0], MessageCannotAssignTask)
        assert ts.send.call_args[0][0].reason.startswith("Not my task")

        __reset(has_subtasks=False)

        ts._react_to_want_to_compute_task(msg)
        assert ts.send.called
        assert isinstance(ts.send.call_args[0][0], MessageCannotAssignTask)
        assert ts.send.call_args[0][0].reason.startswith("No more subtasks")

        __reset(trust_value=0.1)

        ts._react_to_want_to_compute_task(msg)
        assert ts.send.called
        assert isinstance(ts.send.call_args[0][0], MessageCannotAssignTask)
        assert ts.send.call_args[0][0].reason.startswith("Reputation")

        __reset(is_finishing=True)

        ts._react_to_want_to_compute_task(msg)
        assert ts.send.called
        assert isinstance(ts.send.call_args[0][0], MessageWaitingForResults)

        __reset()

        ts._react_to_want_to_compute_task(msg)
        assert not ts.send.called
        assert ts.task_manager.contest_manager.add_contender.called

    def test_send_task_to_compute(self):
        ts = self.__create_task_session()
        ts.send_task_to_compute(Mock())
        assert ts.task_manager.get_next_subtask.called
        ts.send.assert_called_with(Instance(MessageTaskToCompute))

    def test_send_cannot_assign_task(self):
        ts = self.__create_task_session()
        ts.send_cannot_assign_task("deadbeef", "some reason")
        ts.send.assert_called_with(Instance(MessageCannotAssignTask))
        assert ts.send.call_args[0][0].task_id == "deadbeef"
        assert ts.send.call_args[0][0].reason == "some reason"
        ts.disconnect.assert_called_with(ts.DCRNoMoreMessages)

    def test_send_contest_winner(self):
        ts = self.__create_task_session()
        ts.send_contest_winner("deadbeef")
        ts.send.assert_called_with(Instance(MessageContestWinner))
        assert ts.send.call_args[0][0].task_id == "deadbeef"

    def test_react_to_contest_winner(self):
        ts = self.__create_task_session()
        ts.task_computer.is_busy.return_value = False
        ts.task_id = "deadbeef"

        msg = MessageContestWinner("deadbeef")
        dict_repr = msg.dict_repr()
        assert dict_repr == MessageContestWinner(dict_repr=dict_repr).dict_repr()

        ts._react_to_contest_winner(msg)
        ts.send.assert_called_with(Instance(MessageContestWinnerAccept))

        ts.send.called = False
        ts.task_id = "deadbeef_2"
        ts._react_to_contest_winner(msg)
        ts.send.assert_called_with(Instance(MessageContestWinnerReject))

        ts.send.called = False
        ts.task_id = "deadbeef"
        ts.task_computer.is_busy.return_value = True
        ts._react_to_contest_winner(msg)
        ts.send.assert_called_with(Instance(MessageContestWinnerReject))

    def test_react_to_contest_winner_accept(self):
        ts = self.__create_task_session()
        ts.task_id = "deadbeef"

        msg = MessageContestWinnerAccept("deadbeef")
        dict_repr = msg.dict_repr()
        assert dict_repr == MessageContestWinnerAccept(dict_repr=dict_repr).dict_repr()

        ts._react_to_contest_winner_accept(msg)
        ts.task_manager.contest_manager.winner_accepts.assert_called_with("deadbeef", ts.key_id)

        ts.task_id = "deadbeef_2"

        ts._react_to_contest_winner_accept(msg)
        ts.disconnect.assert_called_with(ts.DCRBadProtocol)

    def test_react_to_contest_winner_reject(self):
        ts = self.__create_task_session()
        ts.task_id = "deadbeef"

        msg = MessageContestWinnerReject("deadbeef")
        dict_repr = msg.dict_repr()
        assert dict_repr == MessageContestWinnerReject(dict_repr=dict_repr).dict_repr()

        ts._react_to_contest_winner_reject(msg)
        ts.task_manager.contest_manager.winner_rejects.assert_called_with("deadbeef", ts.key_id)

        ts.task_id = "deadbeef_2"

        ts._react_to_contest_winner_reject(msg)
        ts.disconnect.assert_called_with(ts.DCRBadProtocol)

    @staticmethod
    def __create_task_session():
        conn = Mock()
        tm = Mock()
        tc = Mock()
        tsrv = Mock()

        ts = TaskSession(conn)
        ts.send = Mock()
        ts.dropped = Mock()
        ts.disconnect = Mock()
        ts.key_id = "KEY_ID"
        ts.task_manager = tm
        ts.task_computer = tc
        ts.task_server = tsrv

        return ts








def executor_success(req, success, error):
    success(('filename', 'multihash'))


def executor_recoverable_error(req, success, error):
    error(EnvironmentError())


def executor_error(req, success, error):
    error(Exception())


class TestCreatePackage(unittest.TestCase):

    def setUp(self):
        conn = Mock()
        ts = TaskSession(conn)
        ts.dropped = Mock()
        ts.result_received = Mock()
        ts.send = Mock()
        ts.task_manager = Mock()

        subtask_id = 'xxyyzz'

        res = Mock()
        res.subtask_id = subtask_id
        ts.task_server.get_waiting_task_result.return_value = res

        msg = MessageGetTaskResult(subtask_id=subtask_id)

        self.subtask_id = subtask_id
        self.ts = ts
        self.msg = msg

    @patch('golem.resource.client.AsyncRequestExecutor.run', side_effect=executor_success)
    def test_send_task_result_hash_success(self, _):

        ts = self.ts
        ts._react_to_get_task_result(self.msg)

        assert ts.send.called
        assert not ts.dropped.called

    @patch('golem.resource.client.AsyncRequestExecutor.run', side_effect=executor_recoverable_error)
    def test_send_task_result_hash_recoverable_error(self, _):

        ts = self.ts
        ts._react_to_get_task_result(self.msg)

        assert not ts.send.called
        assert ts.task_server.retry_sending_task_result.called

    @patch('golem.resource.client.AsyncRequestExecutor.run', side_effect=executor_error)
    def test_send_task_result_hash_recoverable_error(self, _):

        ts = self.ts
        ts._react_to_get_task_result(self.msg)

        assert ts.send.called
        assert ts.dropped.called
