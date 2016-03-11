from mock import Mock

from golem.network.p2p.node import Node
from golem.network.transport.message import (MessageRewardPaid, MessageWantToComputeTask, MessageCannotAssignTask,
                                             MessageTaskToCompute, MessageRemoveTask, MessageReportComputedTask)
from golem.task.taskbase import result_types
from golem.task.taskserver import WaitingTaskResult
from golem.task.tasksession import TaskSession, logger
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

    def test_reward_paid(self):
        m = MessageRewardPaid("ABC", 131)
        ts = TaskSession(Mock())
        ts.verified = True
        ts.can_be_not_encrypted.append(m.Type)
        ts.can_be_unsigned.append(m.Type)
        ts.interpret(m)
        ts.task_server.reward_paid.assert_called_with("ABC", 131)

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
        ts2.task_manager.get_next_subtask.return_value = ("CTD", False)
        ts2.interpret(mt)
        ts2.task_server.get_computing_trust.assert_called_with("DEF")
        ms = ts2.conn.send_message.call_args[0][0]
        self.assertIsInstance(ms, MessageCannotAssignTask)
        self.assertEqual(ms.task_id, mt.task_id)
        ts2.task_server.get_computing_trust.return_value = 0.8
        ts2.interpret(mt)
        ms = ts2.conn.send_message.call_args[0][0]
        self.assertIsInstance(ms, MessageTaskToCompute)
        ts2.task_manager.get_next_subtask.return_value = ("CTD", True)
        ts2.interpret(mt)
        ms = ts2.conn.send_message.call_args[0][0]
        self.assertIsInstance(ms, MessageRemoveTask)
        self.assertEqual(ms.task_id, mt.task_id)
        ts2.task_manager.get_next_subtask.return_value = ("CTD", False)
        ts2.task_server.config_desc.max_price = 10
        ts2.interpret(mt)
        ms = ts2.conn.send_message.call_args[0][0]
        self.assertIsInstance(ms, MessageCannotAssignTask)
        self.assertEqual(ms.task_id, mt.task_id)

    def test_send_report_computed_task(self):

        #FIXME We should make this message simple
        ts = TaskSession(Mock())
        ts.verified = True
        ts.task_server.get_node_name.return_value = "ABC"
        n = Node()
        wtr = WaitingTaskResult("xxyyzz", "result", result_types["data"], 13190, 10, 0, "10.10.10.10",
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
