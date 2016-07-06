from mock import Mock, MagicMock

from golem.core.keysauth import KeysAuth
from golem.core.simpleserializer import SimpleSerializer
from golem.network.p2p.node import Node
from golem.network.transport.message import (MessageWantToComputeTask, MessageCannotAssignTask, MessageTaskToCompute,
                                             MessageRemoveTask, MessageReportComputedTask, MessageHello,
                                             MessageSubtaskResultRejected, MessageSubtaskResultAccepted,
                                             MessageTaskResultHash, MessageGetTaskResult)
from golem.task.taskbase import result_types
from golem.task.taskserver import WaitingTaskResult
from golem.task.tasksession import TaskSession, logger, TASK_PROTOCOL_ID
from golem.tools.assertlogs import LogTestCase


class TestTaskSession(LogTestCase):
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
        self.assertTrue(any(["maybe it's not encrypted?" in log for log in l.output]))
        self.assertFalse(any(["Encrypt error" in log for log in l.output]))
        self.assertEqual(res, data)

        ts.task_server.decrypt = Mock(side_effect=ValueError("Different error"))
        with self.assertLogs(logger, level=1) as l:
            res = ts.decrypt(data)
        self.assertTrue(any(["Different error" in log for log in l.output]))
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
        ts2.task_manager.get_next_subtask.return_value = ("CTD", False, False)
        ts2.interpret(mt)
        ts2.task_server.get_computing_trust.assert_called_with("DEF")
        ms = ts2.conn.send_message.call_args[0][0]
        self.assertIsInstance(ms, MessageCannotAssignTask)
        self.assertEqual(ms.task_id, mt.task_id)
        ts2.task_server.get_computing_trust.return_value = 0.8
        ts2.interpret(mt)
        ms = ts2.conn.send_message.call_args[0][0]
        self.assertIsInstance(ms, MessageTaskToCompute)
        ts2.task_manager.get_next_subtask.return_value = ("CTD", True, False)
        ts2.interpret(mt)
        ms = ts2.conn.send_message.call_args[0][0]
        self.assertIsInstance(ms, MessageCannotAssignTask)
        self.assertEqual(ms.task_id, mt.task_id)

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
        keys_auth = KeysAuth()
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
            result=SimpleSerializer.dumps({'stdout': 'xyz'}),
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

    def test_react_to_get_task_result(self):

        conn = Mock()
        ts = TaskSession(conn)
        ts.dropped = Mock()
        ts.result_received = Mock()
        ts.send = Mock()
        trm = ts.task_manager.task_result_manager

        subtask_id = 'xxyyzz'

        res = Mock()
        res.subtask_id = subtask_id
        ts.task_server.get_waiting_task_result.return_value = res

        def create(*args, **kwargs):
            return 'filename', 'multihash'

        def create_raise_env(*args, **kwargs):
            raise EnvironmentError('error')

        def create_raise(*args, **kwargs):
            raise Exception('error')

        msg = MessageGetTaskResult(subtask_id=subtask_id)

        trm.create = create
        ts._react_to_get_task_result(msg)
        assert ts.send.called
        assert not ts.task_server.task_result_sent.called

        trm.create = create_raise_env
        ts._react_to_get_task_result(msg)
        assert ts.task_server.retry_sending_task_result.called

        trm.create = create_raise
        ts._react_to_get_task_result(msg)
        assert ts.task_server.task_result_sent.called

        ts.task_server.get_waiting_task_result.return_value = None
        assert ts.dropped.called
