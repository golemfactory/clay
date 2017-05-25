from datetime import datetime
from pathlib import Path
import random
import time
from unittest import TestCase

from mock import Mock
from mock import patch

from golem.core.common import get_timestamp_utc, timeout_to_deadline
from golem.core.variables import APP_VERSION
from golem.environments.environment import Environment
from golem.environments.environmentsmanager import EnvironmentsManager
from golem.network.p2p.node import Node
from golem.task.taskbase import TaskHeader, ComputeTaskDef
from golem.task.taskkeeper import CompTaskInfo
from golem.task.taskkeeper import TaskHeaderKeeper, CompTaskKeeper, CompSubtaskInfo, logger
from golem.testutils import PEP8MixIn
from golem.testutils import TempDirFixture
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
        self.assertFalse(tk.is_supported(task))
        task["min_version"] = APP_VERSION
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
        task["min_version"] = "120"
        self.assertFalse(tk.is_supported(task))
        task["min_version"] = tk.app_version
        self.assertTrue(tk.is_supported(task))
        task["min_version"] = "abc"
        with self.assertLogs(logger=logger, level=1):
            self.assertFalse(tk.is_supported(task))

    def test_check_version_compatibility(self):
        tk = TaskHeaderKeeper(EnvironmentsManager(), 10.0)
        tk.app_version = '0.4.5'

        with self.assertRaises(ValueError):
            tk.check_version_compatibility('')
        with self.assertRaises(ValueError):
            tk.check_version_compatibility('0')
        with self.assertRaises(ValueError):
            tk.check_version_compatibility('1.5')
        with self.assertRaises(ValueError):
            tk.check_version_compatibility('0.4-alpha+build.2004.01.01')
        with self.assertRaises(ValueError):
            tk.check_version_compatibility('0.4-alpha')
        with self.assertRaises(ValueError):
            tk.check_version_compatibility('0.4-alpha')

        assert not tk.check_version_compatibility('1.5.0')
        assert not tk.check_version_compatibility('1.4.0')
        assert not tk.check_version_compatibility('0.5.0')
        assert not tk.check_version_compatibility('0.4.6')
        assert not tk.check_version_compatibility('0.3.0')

        assert tk.check_version_compatibility('0.4.5')
        assert tk.check_version_compatibility('0.4.1')
        assert tk.check_version_compatibility('0.4.0')
        assert tk.check_version_compatibility('0.4.0-alpha')
        assert tk.check_version_compatibility('0.4.0-alpha+build')
        assert tk.check_version_compatibility('0.4.0-alpha+build.2010')

    def test_change_config(self):
        tk = TaskHeaderKeeper(EnvironmentsManager(), 10.0)
        e = Environment()
        e.accept_tasks = True
        tk.environments_manager.add_environment(e)
        task_header = get_dict_task_header()
        task_header["max_price"] = 9.0
        tk.add_task_header(task_header)
        self.assertNotIn("xyz", tk.supported_tasks)
        self.assertIsNotNone(tk.task_headers["xyz"])
        task_header["task_id"] = "abc"
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
        task_header = get_dict_task_header()
        task_header["task_id"] = "uvw"
        self.assertTrue(tk.add_task_header(task_header))
        self.assertIsNone(tk.get_task())
        e = Environment()
        e.accept_tasks = True
        tk.environments_manager.add_environment(e)
        task_header["task_id"] = "xyz"
        self.assertTrue(tk.add_task_header(task_header))
        th = tk.get_task()
        assert isinstance(th.task_owner, Node)
        self.assertEqual(task_header["task_id"], th.task_id)
        self.assertEqual(task_header["max_price"], th.max_price)
        self.assertEqual(task_header["node_name"], th.node_name)
        self.assertEqual(task_header["task_owner_port"], th.task_owner_port)
        self.assertEqual(task_header["task_owner_key_id"], th.task_owner_key_id)
        self.assertEqual(task_header["environment"], th.environment)
        self.assertEqual(task_header["deadline"], th.deadline)
        self.assertEqual(task_header["subtask_timeout"], th.subtask_timeout)
        self.assertEqual(task_header["max_price"], th.max_price)
        self.assertEqual(task_header["task_id"], th.task_id)

    def test_old_tasks(self):
        tk = TaskHeaderKeeper(EnvironmentsManager(), 10)
        e = Environment()
        e.accept_tasks = True
        tk.environments_manager.add_environment(e)
        task_header = get_dict_task_header()
        task_header["deadline"] = timeout_to_deadline(10)
        assert tk.add_task_header(task_header)
        task_header["deadline"] = timeout_to_deadline(1)
        task_header["task_id"] = "abc"
        assert tk.add_task_header(task_header)
        assert tk.task_headers.get("abc") is not None
        assert tk.task_headers.get("xyz") is not None
        assert tk.removed_tasks.get("abc") is None
        assert tk.removed_tasks.get("xyz") is None
        assert len(tk.supported_tasks) == 2
        time.sleep(1.1)
        tk.remove_old_tasks()
        assert tk.task_headers.get("abc") is None
        assert tk.task_headers.get("xyz") is not None
        assert tk.removed_tasks.get("abc") is not None
        assert tk.removed_tasks.get("xyz") is None
        assert len(tk.supported_tasks) == 1
        assert tk.supported_tasks[0] == "xyz"

    def test_task_header_update(self):
        e = Environment()
        e.accept_tasks = True

        tk = TaskHeaderKeeper(EnvironmentsManager(), 10)
        tk.environments_manager.add_environment(e)

        assert not tk.add_task_header(dict())

        task_header = get_dict_task_header()
        task_id = task_header["task_id"]

        task_header["deadline"] = timeout_to_deadline(10)
        assert tk.add_task_header(task_header)
        assert task_id in tk.supported_tasks
        assert tk.add_task_header(task_header)
        assert task_id in tk.supported_tasks

        task_header["max_price"] = 1
        assert tk.add_task_header(task_header)
        assert task_id not in tk.supported_tasks

        tk.task_headers = {}
        tk.supported_tasks = []

        task_header["max_price"] = 1
        assert tk.add_task_header(task_header)
        assert task_id not in tk.supported_tasks

        task_header['task_id'] = "newtaskID"
        task_header['deadline'] = "WRONG DEADLINE"
        assert not tk.add_task_header(task_header)

    def test_is_correct(self):
        tk = TaskHeaderKeeper(EnvironmentsManager(), 10)
        th = get_dict_task_header()

        correct, err = tk.is_correct(th)
        assert correct
        assert err is None

        th['deadline'] = datetime.now()
        correct, err = tk.is_correct(th)
        assert not correct
        assert err == "Deadline is not a timestamp"

        th['deadline'] = get_timestamp_utc() - 10
        correct, err = tk.is_correct(th)
        assert not correct
        assert err == "Deadline already passed"

        th['deadline'] = get_timestamp_utc() + 20
        correct, err = tk.is_correct(th)
        assert correct
        assert err is None

        th['subtask_timeout'] = "abc"
        correct, err = tk.is_correct(th)
        assert not correct
        assert err == "Subtask timeout is not a number"

        th['subtask_timeout'] = -131
        correct, err = tk.is_correct(th)
        assert not correct
        assert err == "Subtask timeout is less than 0"


def get_dict_task_header():
    return {
        "task_id": "xyz",
        "node_name": "ABC",
        "task_owner": dict(),
        "task_owner_address": "10.10.10.10",
        "task_owner_port": 10101,
        "task_owner_key_id": "kkkk",
        "environment": "DEFAULT",
        "last_checking": time.time(),
        "deadline": timeout_to_deadline(1201),
        "subtask_timeout": 120,
        "max_price": 10,
        "min_version": APP_VERSION
    }


def get_task_header():
    header = get_dict_task_header()
    return TaskHeader(header["node_name"], header["task_id"], header["task_owner_address"],
                      header["task_owner_port"], header["task_owner_key_id"],
                      header["environment"], header["task_owner"], header["deadline"],
                      header["subtask_timeout"], 1024, 1.0, 1000)


class TestCompSubtaskInfo(TestCase):
    def test_init(self):
        csi = CompSubtaskInfo("xxyyzz")
        self.assertIsInstance(csi, CompSubtaskInfo)


class TestCompTaskKeeper(LogTestCase, PEP8MixIn, TempDirFixture):
    PEP8_FILES = [
        "golem/task/taskkeeper.py",
    ]

    def setUp(self):
        super(TestCompTaskKeeper, self).setUp()
        random.seed()

    def test_persistance(self):
        """Tests whether tasks are persistent between restarts."""
        tasks_dir = Path(self.path)
        ctk = CompTaskKeeper(tasks_dir)

        test_headers = []
        for x in range(100):
            header = get_task_header()
            header.task_id = "test%d-%d" % (x, random.random()*1000)
            test_headers.append(header)
            ctk.add_request(header, int(random.random()*100))
        del ctk

        ctk = CompTaskKeeper(tasks_dir)
        for header in test_headers:
            self.assertIn(header.task_id, ctk.active_tasks)

    @patch('golem.task.taskkeeper.CompTaskKeeper.dump')
    def test_comp_keeper(self, dump_mock):
        ctk = CompTaskKeeper(Path('ignored'))
        header = get_task_header()
        header.task_id = "xyz"
        with self.assertRaises(TypeError):
            ctk.add_request(header, "not a number")
        with self.assertRaises(ValueError):
            ctk.add_request(header, -2)
        ctk.add_request(header, 7200)
        self.assertEqual(ctk.active_tasks["xyz"].requests, 1)
        self.assertEqual(ctk.active_tasks["xyz"].price, 7200)
        self.assertEqual(ctk.active_tasks["xyz"].header, header)
        ctk.add_request(header, 23)
        self.assertEqual(ctk.active_tasks["xyz"].requests, 2)
        self.assertEqual(ctk.active_tasks["xyz"].price, 7200)
        self.assertEqual(ctk.active_tasks["xyz"].header, header)
        self.assertEqual(ctk.get_value("xyz", 1), 2)
        header.task_id = "xyz2"
        ctk.add_request(header, 25000)
        self.assertEqual(ctk.active_tasks["xyz2"].price, 25000)
        self.assertEqual(ctk.get_value("xyz2", 4.5), 32)
        header.task_id = "xyz"
        thread = get_task_header()
        thread.task_id = "qaz123WSX"
        with self.assertRaises(ValueError):
            ctk.add_request(thread, -1)
        with self.assertRaises(TypeError):
            ctk.add_request(thread, '1')
        ctk.add_request(thread, 12)
        header = get_task_header()
        header.task_id = "qwerty"
        ctk.active_tasks["qwerty"] = CompTaskInfo(header, 12)
        ctk.active_tasks["qwerty"].price = "abc"
        with self.assertRaises(TypeError):
            ctk.get_value('qwerty', 12)
        self.assertEqual(ctk.get_value(thread.task_id, 600), 2)

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

    def test_receive_subtask_problems(self):
        ctk = CompTaskKeeper(Path(self.path), False)
        th = get_task_header()
        ctk.add_request(th, 5)
        ctd = ComputeTaskDef()
        ctd.task_id = "xyz"
        ctd.subtask_id = "abc"
        ctk.receive_subtask(ctd)
        assert ctk.active_tasks["xyz"].requests == 0
        assert ctk.subtask_to_task["abc"] == "xyz"
        ctd2 = ComputeTaskDef()
        ctd2.task_id = "xyz"
        ctd2.subtask_id = "def"
        ctk.receive_subtask(ctd2)
        assert ctk.active_tasks["xyz"].requests == 0
        assert ctk.subtask_to_task.get("def") is None
        assert ctk.subtask_to_task["abc"] == "xyz"
        ctk.active_tasks["xyz"].requests = 1
        ctk.receive_subtask(ctd)
        assert ctk.active_tasks["xyz"].requests == 1

    @patch('golem.task.taskkeeper.CompTaskKeeper.dump')
    def test_get_task_env(self, dump_mock):
        ctk = CompTaskKeeper(Path('ignored'))
        with self.assertLogs(logger, level="WARNING"):
            assert ctk.get_task_env("task1") is None

        header = get_task_header()
        ctk.add_request(header, 4002)

        header = get_task_header()
        header.task_id = "abc"
        header.environment = "NOTDEFAULT"
        ctk.add_request(header, 4002)

        assert ctk.get_task_env("abc") == "NOTDEFAULT"
        assert ctk.get_task_env("xyz") == "DEFAULT"
