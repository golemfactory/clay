from mock import Mock

from golem.task.taskserver import TaskServer, WaitingTaskResult, TaskConnTypes
from golem.network.p2p.node import Node
from golem.core.keysauth import EllipticalKeysAuth
from golem.tools.testwithappconfig import TestWithKeysAuth
from golem.clientconfigdescriptor import ClientConfigDescriptor


class TestTaskServer(TestWithKeysAuth):
    def test_request(self):
        ccd = ClientConfigDescriptor()
        ccd.min_price = 10
        n = Node()
        ka = EllipticalKeysAuth()
        ts = TaskServer(n, ccd, ka, Mock())
        ts.client.get_suggested_addr.return_value = "10.10.10.10"
        self.assertIsInstance(ts, TaskServer)
        self.assertEqual(0, ts.request_task())
        n2 = Node()
        n2.prv_addr = "10.10.10.10"
        n2.port = 10101
        task_header = self.__get_example_task_header()
        task_header["task_owner"] = n2
        ts.add_task_header(task_header)
        self.assertEqual("uvw", ts.request_task())

    def test_send_results(self):
        ccd = ClientConfigDescriptor()
        ccd.min_price = 11
        n = Node()
        ka = EllipticalKeysAuth()
        ts = TaskServer(n, ccd, ka, Mock())
        ts.client.get_suggested_addr.return_value = "10.10.10.10"
        results = {"data": "", "result_type": 0}
        task_header = self.__get_example_task_header()
        task_header["id"] = "xyz"
        ts.add_task_header(task_header)
        th = ts.request_task()
        self.assertTrue(ts.send_results("xxyyzz", "xyz", results, 40, "10.10.10.10", 10101, "key", n, "node_name"))
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
        ts.client.add_to_waiting_payments.assert_called_with("xyz", "key", 440)

    def __get_example_task_header(self):
        node = Node()
        task_header = {"id": "uvw",
                       "node_name": "ABC",
                       "address": "10.10.10.10",
                       "port": 10101,
                       "key_id": "kkkk",
                       "environment": "DEFAULT",
                       "task_owner": node,
                       "task_owner_port": 10101,
                       "task_owner_key_id": "key",
                       "ttl": 1201,
                       "subtask_timeout": 120,
                       "max_price": 20
                       }
        return task_header

    def test_connection_for_task_request_established(self):
        ccd = ClientConfigDescriptor()
        ccd.min_price = 11
        n = Node()
        ka = EllipticalKeysAuth()
        ts = TaskServer(n, ccd, ka, Mock())
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

