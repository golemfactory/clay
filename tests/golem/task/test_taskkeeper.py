import time
from unittest import TestCase

from mock import Mock

from golem.environments.environment import Environment
from golem.environments.environmentsmanager import EnvironmentsManager
from golem.task.taskbase import TaskHeader, ComputeTaskDef
from golem.task.taskkeeper import TaskHeaderKeeper, CompTaskKeeper, CompSubtaskInfo, logger
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
        task_header = get_task_header()
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

    def test_get_task(self):
        tk = TaskHeaderKeeper(EnvironmentsManager(), 10)

        self.assertIsNone(tk.get_task())
        task_header = get_task_header()
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


def get_task_header():
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


class TestCompSubtaskInfo(TestCase):
    def test_init(self):
        csi = CompSubtaskInfo("xxyyzz")
        self.assertIsInstance(csi, CompSubtaskInfo)


class TestCompTaskKeeper(LogTestCase):
    def test_comp_keeper(self):
        ctk = CompTaskKeeper()
        header = get_task_header()
        header = TaskHeader(header["node_name"], header["id"], header["address"], header["port"], header["key_id"],
                            header["environment"], header["task_owner"], header["ttl"], header["subtask_timeout"],
                            1024, 1.0, 1000)
        header.task_id = "xyz"
        ctk.add_request(header, 5)
        self.assertEqual(ctk.active_tasks["xyz"].requests, 1)
        self.assertEqual(ctk.active_tasks["xyz"].price, 5)
        self.assertEqual(ctk.active_tasks["xyz"].header, header)
        ctk.add_request(header, 23)
        self.assertEqual(ctk.active_tasks["xyz"].requests, 2)
        self.assertEqual(ctk.active_tasks["xyz"].price, 5)
        self.assertEqual(ctk.active_tasks["xyz"].header, header)
        self.assertIsNone(ctk.get_subtask_ttl("abc"))
        ctd = ComputeTaskDef()
        with self.assertLogs(logger, level="WARNING"):
            self.assertFalse(ctk.receive_subtask(ctd))
        with self.assertLogs(logger, level="WARNING"):
            self.assertIsNone(ctk.get_node_for_task_id("abc"))
        with self.assertLogs(logger, level="WARNING"):
            self.assertIsNone(ctk.get_value("abc", 10))

        with self.assertLogs(logger, level="WARNING"):
            ctk.request_failure("abc")
        ctk.request_failure("xyz")
        self.assertEqual(ctk.active_tasks["xyz"].requests, 1)

        with self.assertLogs(logger, level="WARNING"):
            ctk.remove_task("abc")
        self.assertIsNotNone(ctk.active_tasks.get("xyz"))
        with self.assertNoLogs(logger, level="WARNING"):
            ctk.remove_task("xyz")
        self.assertIsNone(ctk.active_tasks.get("xyz"))

        header.ttl = -1
        ctk.add_request(header, 23)
        self.assertEqual(ctk.active_tasks["xyz"].requests, 1)
        ctk.remove_old_tasks()
        self.assertIsNone(ctk.active_tasks.get("xyz"))
        ctk.add_request(header, 23)
        ctd.task_id = "xyz"
        ctd.subtask_id = "xxyyzz"
        ctk.receive_subtask(ctd)
        ctk.remove_old_tasks()
        self.assertIsNotNone(ctk.active_tasks.get("xyz"))





