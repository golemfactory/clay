import datetime

from mock import Mock

from golem.environments.environment import Environment
from golem.environments.environmentsmanager import EnvironmentsManager
from golem.task.taskkeeper import TaskKeeper, logger
from golem.tools.assertlogs import LogTestCase


class TestTaskKeeper(LogTestCase):
    def test_init(self):
        tk = TaskKeeper(EnvironmentsManager(), 10.0)
        self.assertIsInstance(tk, TaskKeeper)

    def test_is_supported(self):
        tk = TaskKeeper(EnvironmentsManager(), 10.0)
        self.assertFalse(tk.is_supported({}))
        task = {"environment": Environment.get_id(), 'max_price': 0}
        self.assertFalse(tk.is_supported(task))
        e = Environment()
        e.accept_tasks = True
        tk.environments_manager.add_environment(e)
        self.assertFalse(tk.is_supported(task))
        task["max_price"] = 10.0
        self.assertTrue(tk.is_supported(task))
        task["max_price"] = 10.5
        self.assertTrue(tk.is_supported(task))
        config_desc = Mock()
        config_desc.min_price = 13.0
        tk.change_config(config_desc)
        self.assertFalse(tk.is_supported(task))

    def test_get_task(self):
        tk = TaskKeeper(EnvironmentsManager(), 10)

        self.assertIsNone(tk.get_task(5))
        task_header = {"id": "uvw",
                       "node_name": "ABC",
                       "address": "10.10.10.10",
                       "port": 10101,
                       "key_id": "kkkk",
                       "environment": "DEFAULT",
                       "task_owner": "task_owner",
                       "ttl": 1201,
                       "subtask_timeout": 120,
                       "max_price": 10
                       }
        self.assertTrue(tk.add_task_header(task_header))
        self.assertIsNone(tk.get_task(5))
        e = Environment()
        e.accept_tasks = True
        tk.environments_manager.add_environment(e)
        task_header["id"] = "xyz"
        self.assertTrue(tk.add_task_header(task_header))
        th = tk.get_task(5)
        self.assertEqual(task_header["id"], th.task_id)
        self.assertEqual(task_header["max_price"], th.max_price)
        self.assertEqual(task_header["node_name"], th.node_name)
        self.assertEqual(task_header["port"], th.task_owner_port)
        self.assertEqual(task_header["key_id"], th.task_owner_key_id)
        self.assertEqual(task_header["environment"], th.environment)
        self.assertEqual(task_header["task_owner"], th.task_owner)
        self.assertEqual(task_header["ttl"], th.ttl)
        self.assertEqual(task_header["subtask_timeout"], th.subtask_timeout)
        self.assertEqual(task_header["max_price"], th.max_price)
        self.assertEqual(tk.active_tasks[th.task_id]["price"], 5)
        self.assertEqual(tk.active_tasks[th.task_id]["header"], th)
        self.assertEqual(tk.active_requests[th.task_id], 1)
        th = tk.get_task(5)
        self.assertEqual(task_header["id"], th.task_id)
        self.assertEqual(tk.active_tasks[th.task_id]["header"], th)
        self.assertEqual(tk.active_requests[th.task_id], 2)

    def test_get_receiver_for_task_verification_results(self):
        tk = TaskKeeper(EnvironmentsManager(), 10)
        e = Environment()
        e.accept_tasks = True
        tk.environments_manager.add_environment(e)
        task_header = {"id": "xyz",
                       "node_name": "ABC",
                       "address": "10.10.10.10",
                       "port": 10101,
                       "key_id": "kkkk",
                       "environment": "DEFAULT",
                       "task_owner": "task_owner",
                       "ttl": 1201,
                       "subtask_timeout": 120,
                       "max_price": 10
                       }
        tk.add_task_header(task_header)
        th = tk.get_task(5)
        key_id = tk.get_receiver_for_task_verification_result(th.task_id)
        self.assertEqual(key_id, "kkkk")

    def test_add_to_verification(self):
        tk = TaskKeeper(EnvironmentsManager(), 10)
        task_header = {"id": "xyz",
                       "node_name": "ABC",
                       "address": "10.10.10.10",
                       "port": 10101,
                       "key_id": "kkkk",
                       "environment": "DEFAULT",
                       "task_owner": "task_owner",
                       "ttl": 1201,
                       "subtask_timeout": 120,
                       "max_price": 10
                       }

        e = Environment()
        e.accept_tasks = True
        tk.environments_manager.add_environment(e)
        tk.add_task_header(task_header)
        with self.assertLogs(logger, level=1):
            price = tk.add_to_verification("uuvvww", "xyz", 100)
        self.assertEqual(price, 0)
        th = tk.get_task(5)
        price = tk.add_to_verification("xxyyzz", "xyz", 100)
        self.assertEqual(price, 500)
        sv = tk.waiting_for_verification["xxyyzz"]
        self.assertEqual(sv[0], "xyz")
        self.assertLessEqual(sv[1], datetime.datetime.now())
        self.assertLessEqual(sv[2], datetime.datetime.now() + datetime.timedelta(0, tk.verification_timeout))



