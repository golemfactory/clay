import datetime
import time

from mock import Mock

from golem.environments.environment import Environment
from golem.environments.environmentsmanager import EnvironmentsManager
from golem.task.taskkeeper import TaskHeaderKeeper, logger
from golem.tools.assertlogs import LogTestCase


class TestTaskHeaderKeeper(LogTestCase):
    def test_init(self):
        tk = TaskHeaderKeeper(EnvironmentsManager(), 10.0)
        self.assertIsInstance(tk, TaskHeaderKeeper)

    def test_is_supported(self):
        tk = TaskHeaderKeeper(EnvironmentsManager(), 10.0)
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
        config_desc.min_price = 10.0
        tk.change_config(config_desc)
        self.assertTrue(tk.is_supported(task))
        task["min_version"] = 120
        self.assertFalse(tk.is_supported(task))
        task["min_version"] = tk.app_version
        self.assertTrue(tk.is_supported(task))
        task["min_version"] = "abc"
        with self.assertLogs(logger=logger, level=1):
            self.assertFalse(tk.is_supported(task))

    def test_change_config(self):
        tk = TaskHeaderKeeper(EnvironmentsManager(), 10.0)
        e = Environment()
        e.accept_tasks = True
        tk.environments_manager.add_environment(e)
        task_header = self.__get_task_header()
        task_header["max_price"] = 9.0
        tk.add_task_header(task_header)
        self.assertNotIn("xyz", tk.supported_tasks)
        self.assertIsNotNone(tk.task_headers["xyz"])
        task_header["id"] = "abc"
        task_header["max_price"] = 10.0
        tk.add_task_header(task_header)
        self.assertIn("abc", tk.supported_tasks)
        self.assertIsNotNone(tk.task_headers["abc"])
        config_desc = Mock()
        config_desc.min_price = 10.0
        tk.change_config(config_desc)
        self.assertNotIn("xyz", tk.supported_tasks)
        self.assertIn("abc", tk.supported_tasks)
        config_desc.min_price = 8.0
        tk.change_config(config_desc)
        self.assertIn("xyz", tk.supported_tasks)
        self.assertIn("abc", tk.supported_tasks)
        config_desc.min_price = 11.0
        tk.change_config(config_desc)
        self.assertNotIn("xyz", tk.supported_tasks)
        self.assertNotIn("abc", tk.supported_tasks)

    def __get_task_header(self):
        return {"id": "xyz",
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

    def test_get_task(self):
        tk = TaskHeaderKeeper(EnvironmentsManager(), 10)

        self.assertIsNone(tk.get_task())
        task_header = self.__get_task_header()
        task_header["id"] = "uvw"
        self.assertTrue(tk.add_task_header(task_header))
        self.assertIsNone(tk.get_task())
        e = Environment()
        e.accept_tasks = True
        tk.environments_manager.add_environment(e)
        task_header["id"] = "xyz"
        self.assertTrue(tk.add_task_header(task_header))
        th = tk.get_task()
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
        th = tk.get_task()
        self.assertEqual(task_header["id"], th.task_id)
