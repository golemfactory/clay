from datetime import datetime
from golem_messages.message import ComputeTaskDef
from pathlib import Path
import random
import time
from unittest import TestCase
import unittest.mock as mock

import golem
from golem.core.common import get_timestamp_utc, timeout_to_deadline
from golem.core.idgenerator import generate_id, generate_new_id_from_id
from golem.environments.environment import Environment, UnsupportReason,\
    SupportStatus
from golem.environments.environmentsmanager import EnvironmentsManager
from golem.network.p2p.node import Node
from golem.task.taskbase import TaskHeader
from golem.task.taskkeeper import CompTaskInfo
from golem.task.taskkeeper import TaskHeaderKeeper, CompTaskKeeper,\
    CompSubtaskInfo, logger
from golem.testutils import PEP8MixIn
from golem.testutils import TempDirFixture
from golem.tools.assertlogs import LogTestCase
from golem.utils import encode_hex


def async_run(request, success=None, error=None):
    try:
        result = request.method(*request.args, **request.kwargs)
    except Exception as exc:
        if error:
            error(exc)
    else:
        if success:
            success(result)


class TestTaskHeaderKeeper(LogTestCase):
    def test_init(self):
        tk = TaskHeaderKeeper(EnvironmentsManager(), 10.0)
        self.assertIsInstance(tk, TaskHeaderKeeper)

    def test_is_supported(self):
        tk = TaskHeaderKeeper(EnvironmentsManager(), 10.0)
        self.assertFalse(tk.check_support({}))
        task = {"environment": Environment.get_id(), 'max_price': 0}
        supported = tk.check_support(task)
        self.assertFalse(supported)
        self.assertIn(UnsupportReason.ENVIRONMENT_MISSING, supported.desc)
        e = Environment()
        e.accept_tasks = True
        tk.environments_manager.add_environment(e)
        supported = tk.check_support(task)
        self.assertFalse(supported)
        self.assertIn(UnsupportReason.MAX_PRICE, supported.desc)
        task["max_price"] = 10.0
        supported = tk.check_support(task)
        self.assertFalse(supported)
        self.assertIn(UnsupportReason.APP_VERSION, supported.desc)
        task["min_version"] = golem.__version__
        self.assertTrue(tk.check_support(task))
        task["max_price"] = 10.5
        self.assertTrue(tk.check_support(task))
        config_desc = mock.Mock()
        config_desc.min_price = 13.0
        tk.change_config(config_desc)
        self.assertFalse(tk.check_support(task))
        config_desc.min_price = 10.0
        tk.change_config(config_desc)
        self.assertTrue(tk.check_support(task))
        task["min_version"] = "120"
        self.assertFalse(tk.check_support(task))
        task["min_version"] = tk.app_version
        self.assertTrue(tk.check_support(task))
        task["min_version"] = "abc"
        with self.assertLogs(logger=logger, level='WARNING'):
            self.assertFalse(tk.check_support(task))

    def test_check_version_compatibility(self):
        tk = TaskHeaderKeeper(EnvironmentsManager(), 10.0)
        tk.app_version = '0.4.5-dev+232.138018'

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

    @mock.patch('golem.task.taskarchiver.TaskArchiver')
    def test_change_config(self, tar):
        tk = TaskHeaderKeeper(EnvironmentsManager(), 10.0, task_archiver=tar)
        e = Environment()
        e.accept_tasks = True
        tk.environments_manager.add_environment(e)
        task_header = get_dict_task_header()
        task_id = task_header["task_id"]
        task_header["max_price"] = 9.0
        tk.add_task_header(task_header)
        self.assertNotIn(task_id, tk.supported_tasks)
        self.assertIsNotNone(tk.task_headers[task_id])
        task_header = get_dict_task_header("abc")
        task_id2 = task_header["task_id"]
        task_header["max_price"] = 10.0
        tk.add_task_header(task_header)
        self.assertIn(task_id2, tk.supported_tasks)
        self.assertIsNotNone(tk.task_headers[task_id2])
        config_desc = mock.Mock()
        config_desc.min_price = 10.0
        tk.change_config(config_desc)
        self.assertNotIn(task_id, tk.supported_tasks)
        self.assertIn(task_id2, tk.supported_tasks)
        config_desc.min_price = 8.0
        tk.change_config(config_desc)
        self.assertIn(task_id, tk.supported_tasks)
        self.assertIn(task_id2, tk.supported_tasks)
        config_desc.min_price = 11.0
        tk.change_config(config_desc)
        self.assertNotIn(task_id, tk.supported_tasks)
        self.assertNotIn(task_id2, tk.supported_tasks)
        # Make sure the tasks stats are properly archived
        tar.reset_mock()
        config_desc.min_price = 9.5
        tk.change_config(config_desc)
        self.assertNotIn(task_id, tk.supported_tasks)
        self.assertIn(task_id2, tk.supported_tasks)
        tar.add_support_status.assert_any_call(
            task_id, SupportStatus(False, {UnsupportReason.MAX_PRICE: 9.0}))
        tar.add_support_status.assert_any_call(
            task_id2, SupportStatus(True, {}))

    def test_get_task(self):
        tk = TaskHeaderKeeper(EnvironmentsManager(), 10)

        self.assertIsNone(tk.get_task())
        task_header = get_dict_task_header("uvw")
        self.assertTrue(tk.add_task_header(task_header))
        self.assertIsNone(tk.get_task())
        e = Environment()
        e.accept_tasks = True
        tk.environments_manager.add_environment(e)
        task_header2 = get_dict_task_header("xyz")
        self.assertTrue(tk.add_task_header(task_header2))
        th = tk.get_task()
        assert isinstance(th.task_owner, Node)
        self.assertEqual(task_header2["max_price"], th.max_price)
        self.assertEqual(task_header2["node_name"], th.node_name)
        self.assertEqual(task_header2["task_owner_port"], th.task_owner_port)
        self.assertEqual(task_header2["task_owner_key_id"],
                         th.task_owner_key_id)
        self.assertEqual(task_header2["environment"], th.environment)
        self.assertEqual(task_header2["deadline"], th.deadline)
        self.assertEqual(task_header2["subtask_timeout"], th.subtask_timeout)
        self.assertEqual(task_header2["max_price"], th.max_price)
        self.assertEqual(task_header2["task_id"], th.task_id)

    def test_old_tasks(self):
        tk = TaskHeaderKeeper(EnvironmentsManager(), 10)
        e = Environment()
        e.accept_tasks = True
        tk.environments_manager.add_environment(e)
        task_header = get_dict_task_header()
        task_header["deadline"] = timeout_to_deadline(10)
        assert tk.add_task_header(task_header)
        task_id = task_header["task_id"]
        task_header2 = get_dict_task_header("abc")
        task_header2["deadline"] = timeout_to_deadline(1)
        task_id2 = task_header2["task_id"]
        assert tk.add_task_header(task_header2)
        assert tk.task_headers.get(task_id2) is not None
        assert tk.task_headers.get(task_id) is not None
        assert tk.removed_tasks.get(task_id2) is None
        assert tk.removed_tasks.get(task_id) is None
        assert len(tk.supported_tasks) == 2
        time.sleep(1.1)
        tk.remove_old_tasks()
        assert tk.task_headers.get(task_id2) is None
        assert tk.task_headers.get(task_id) is not None
        assert tk.removed_tasks.get(task_id2) is not None
        assert tk.removed_tasks.get(task_id) is None
        assert len(tk.supported_tasks) == 1
        assert tk.supported_tasks[0] == task_id

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

        task_header2 = get_dict_task_header("newtaskId")
        task_header2['deadline'] = "WRONG DEADLINE"
        assert not tk.add_task_header(task_header2)

    @mock.patch('golem.task.taskarchiver.TaskArchiver')
    def test_task_header_update_stats(self, tar):
        e = Environment()
        e.accept_tasks = True
        tk = TaskHeaderKeeper(EnvironmentsManager(), 10, task_archiver=tar)
        tk.environments_manager.add_environment(e)
        task_header = get_dict_task_header("good")
        assert tk.add_task_header(task_header)
        tar.add_task.assert_called_with(mock.ANY)
        task_id = task_header["task_id"]
        tar.add_support_status.assert_any_call(
            task_id, SupportStatus(True, {}))
        tar.reset_mock()
        task_header2 = get_dict_task_header("bad")
        task_id2 = task_header2['task_id']
        task_header2["max_price"] = 1.0
        assert tk.add_task_header(task_header2)
        tar.add_task.assert_called_with(mock.ANY)
        tar.add_support_status.assert_any_call(
            task_id2, SupportStatus(False, {UnsupportReason.MAX_PRICE: 1.0}))

    def test_is_correct(self):
        tk = TaskHeaderKeeper(EnvironmentsManager(), 10)
        th = get_dict_task_header()

        correct, err = tk.is_correct(th)
        assert correct
        assert err is None
        tk.check_correct(th)  # shouldn't raise

        th['deadline'] = datetime.now()
        correct, err = tk.is_correct(th)
        assert not correct
        assert err == "Deadline is not a timestamp"
        with self.assertRaisesRegex(TypeError, "Deadline is not a timestamp"):
            tk.check_correct(th)

        th['deadline'] = get_timestamp_utc() - 10
        correct, err = tk.is_correct(th)
        assert not correct
        assert "Deadline already passed" in err
        with self.assertRaisesRegex(TypeError, "Deadline already passed"):
            tk.check_correct(th)

        th['deadline'] = get_timestamp_utc() + 20
        correct, err = tk.is_correct(th)
        assert correct
        assert err is None
        tk.check_correct(th)  # shouldn't raise

        th['subtask_timeout'] = "abc"
        correct, err = tk.is_correct(th)
        assert not correct
        assert "Subtask timeout is not a number" in err
        with self.assertRaisesRegex(TypeError,
                                    "Subtask timeout is not a number"):
            tk.check_correct(th)

        th['subtask_timeout'] = -131
        correct, err = tk.is_correct(th)
        assert not correct
        assert "Subtask timeout is less than 0" in err
        with self.assertRaisesRegex(TypeError,
                                    "Subtask timeout is less than 0"):
            tk.check_correct(th)

    def test_task_limit(self):
        tk = TaskHeaderKeeper(EnvironmentsManager(), 10)
        limit = tk.max_tasks_per_requestor

        thd = get_dict_task_header("ta")
        thd["deadline"] = timeout_to_deadline(0.1)
        tk.add_task_header(thd)

        ids = [thd["task_id"]]
        for i in range(1, limit):
            thd = get_dict_task_header("ta")
            ids.append(thd["task_id"])
            tk.add_task_header(thd)
        last_add_time = time.time()

        for id_ in ids:
            self.assertIn(id_, tk.task_headers)

        thd = get_dict_task_header("tb0")
        tb_id = thd["task_id"]
        tk.add_task_header(thd)

        for id_ in ids:
            self.assertIn(id_, tk.task_headers)

        self.assertIn(tb_id, tk.task_headers)

        while time.time() == last_add_time:
            time.sleep(0.1)

        thd = get_dict_task_header("ta")
        new_task_id = thd["task_id"]
        tk.add_task_header(thd)
        self.assertNotIn(new_task_id, tk.task_headers)

        for id_ in ids:
            self.assertIn(id_, tk.task_headers)
        self.assertIn(tb_id, tk.task_headers)

        time.sleep(0.1)
        tk.remove_old_tasks()

        thd = get_dict_task_header("ta")
        new_task_id = thd["task_id"]
        tk.add_task_header(thd)
        self.assertIn(new_task_id, tk.task_headers)

        self.assertNotIn(ids[0], tk.task_headers)
        for i in range(1, limit):
            self.assertIn(ids[i], tk.task_headers)
        self.assertIn(tb_id, tk.task_headers)

    def test_check_max_tasks_per_owner(self):
        tk = TaskHeaderKeeper(EnvironmentsManager(), 10,
                              max_tasks_per_requestor=10)
        limit = tk.max_tasks_per_requestor
        new_limit = 3

        ids = []
        for i in range(new_limit):
            thd = get_dict_task_header("ta")
            ids.append(thd["task_id"])
            tk.add_task_header(thd)
        last_add_time = time.time()

        thd = get_dict_task_header("tb0")
        tb0_id = thd["task_id"]
        tk.add_task_header(thd)

        for id_ in ids:
            self.assertIn(id_, tk.task_headers)
        self.assertIn(tb0_id, tk.task_headers)

        while time.time() == last_add_time:
            time.sleep(0.1)

        new_ids = []
        for i in range(new_limit, limit):
            thd = get_dict_task_header("ta")
            new_ids.append(thd["task_id"])
            tk.add_task_header(thd)

        for id_ in ids + new_ids:
            self.assertIn(id_, tk.task_headers)
        self.assertIn(tb0_id, tk.task_headers)
        self.assertEqual(limit + 1, len(tk.task_headers))

        # shouldn't remove any tasks
        tk.check_max_tasks_per_owner(thd['task_owner_key_id'])

        for id_ in ids + new_ids:
            self.assertIn(id_, tk.task_headers)
        self.assertIn(tb0_id, tk.task_headers)
        self.assertEqual(limit + 1, len(tk.task_headers))

        tk.max_tasks_per_requestor = new_limit

        # should remove ta{3..9}
        tk.check_max_tasks_per_owner(thd['task_owner_key_id'])

        for id_ in ids:
            self.assertIn(id_, tk.task_headers)
        self.assertIn(tb0_id, tk.task_headers)
        self.assertEqual(new_limit + 1, len(tk.task_headers))

    def test_get_unsupport_reasons(self):
        tk = TaskHeaderKeeper(EnvironmentsManager(), 10)
        e = Environment()
        e.accept_tasks = True
        tk.environments_manager.add_environment(e)

        # Supported task
        thd = get_dict_task_header("good")
        tk.add_task_header(thd)

        # Wrong version
        thd = get_dict_task_header("wrong version")
        thd["min_version"] = "42.0.17"
        tk.add_task_header(thd)

        # Wrong environment
        thd = get_dict_task_header("wrong env")
        thd["environment"] = "UNKNOWN"
        tk.add_task_header(thd)

        # Wrong price
        thd = get_dict_task_header("wrong price")
        thd["max_price"] = 1
        tk.add_task_header(thd)

        # Wrong price and version
        thd = get_dict_task_header("wrong price and version")
        thd["min_version"] = "42.0.17"
        thd["max_price"] = 1
        tk.add_task_header(thd)

        # And one more with wrong version
        thd = get_dict_task_header("wrong version 2")
        thd["min_version"] = "42.0.44"
        tk.add_task_header(thd)

        reasons = tk.get_unsupport_reasons()
        # 3 tasks with wrong version
        self.assertIn({'avg': golem.__version__,
                       'reason': 'app_version',
                       'ntasks': 3}, reasons)
        # 2 tasks with wrong price
        self.assertIn({'avg': 7, 'reason': 'max_price', 'ntasks': 2}, reasons)
        # 1 task with wrong environment
        self.assertIn({'avg': None,
                       'reason': 'environment_missing',
                       'ntasks': 1}, reasons)
        self.assertIn({'avg': None,
                       'reason': 'environment_not_accepting_tasks',
                       'ntasks': 1}, reasons)

    def test_get_owner(self):
        tk = TaskHeaderKeeper(EnvironmentsManager(), 10)
        header = get_dict_task_header()
        owner = header["task_owner_key_id"]
        key_id = header["task_id"]
        tk.add_task_header(header)
        assert tk.get_owner(key_id) == owner
        assert tk.get_owner("UNKNOWN") is None


def get_dict_task_header(key_id_seed="kkk"):
    key_id = str.encode(key_id_seed)
    return {
        "task_id": generate_id(key_id),
        "node_name": "ABC",
        "task_owner": {"node_name": "Bob's node"},
        "task_owner_address": "10.10.10.10",
        "task_owner_port": 10101,
        "task_owner_key_id": encode_hex(key_id),
        "environment": "DEFAULT",
        "last_checking": time.time(),
        "deadline": timeout_to_deadline(1201),
        "subtask_timeout": 120,
        "max_price": 10,
        "min_version": golem.__version__
    }


def get_task_header():
    header = get_dict_task_header()
    return TaskHeader(header["node_name"], header["task_id"],
                      header["task_owner_address"],
                      header["task_owner_port"], header["task_owner_key_id"],
                      header["environment"], header["task_owner"],
                      header["deadline"],
                      header["subtask_timeout"], 1024, 1.0, 1000,
                      header['max_price'])


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

    def _dump_some_tasks(self, tasks_dir):
        ctk = CompTaskKeeper(tasks_dir)

        test_headers = []
        test_subtasks_ids = []
        for x in range(10):
            header = get_task_header()
            header.deadline = timeout_to_deadline(1)
            header.subtask_timeout = 1.5
            header.resource_size = 1

            test_headers.append(header)
            ctk.add_request(header, int(random.random() * 100))

            ctd = ComputeTaskDef()
            ctd['task_id'] = header.task_id
            ctd['subtask_id'] = generate_new_id_from_id(header.task_id)
            ctd['deadline'] = timeout_to_deadline(header.subtask_timeout - 0.5)
            self.assertTrue(ctk.receive_subtask(ctd))
            test_subtasks_ids.append(ctd['subtask_id'])
        del ctk

        another_ctk = CompTaskKeeper(tasks_dir)
        for (subtask_id, header) in zip(test_subtasks_ids, test_headers):
            self.assertIn(subtask_id, another_ctk.subtask_to_task)
            self.assertIn(header.task_id, another_ctk.active_tasks)

    @mock.patch('golem.task.taskkeeper.async_run', async_run)
    def test_persistence(self):
        """Tests whether tasks are persistent between restarts."""
        tasks_dir = Path(self.path)
        self._dump_some_tasks(tasks_dir)

    @mock.patch('golem.task.taskkeeper.async_run', async_run)
    @mock.patch('golem.task.taskkeeper.common.get_timestamp_utc')
    def test_remove_old_tasks(self, timestamp):
        timestamp.return_value = time.time()
        tasks_dir = Path(self.path)
        self._dump_some_tasks(tasks_dir)

        ctk = CompTaskKeeper(tasks_dir)
        ctk.remove_old_tasks()

        self.assertTrue(any(ctk.active_tasks))
        self.assertTrue(any(ctk.subtask_to_task))
        timestamp.return_value = time.time() + 1
        ctk.remove_old_tasks()
        self.assertTrue(any(ctk.active_tasks))
        self.assertTrue(any(ctk.subtask_to_task))
        timestamp.return_value = time.time() + 300
        ctk.remove_old_tasks()
        self.assertTrue(not any(ctk.active_tasks))
        self.assertTrue(not any(ctk.subtask_to_task))

    @mock.patch('golem.task.taskkeeper.CompTaskKeeper.dump')
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
        task_id = th.task_id
        ctk.add_request(th, 5)
        subtask_id = generate_new_id_from_id(task_id)
        ctd = ComputeTaskDef()
        ctd['task_id'] = task_id
        ctd['subtask_id'] = subtask_id
        ctd['deadline'] = timeout_to_deadline(th.subtask_timeout - 1)
        ctk.receive_subtask(ctd)
        assert ctk.active_tasks[task_id].requests == 0
        assert ctk.subtask_to_task[subtask_id] == task_id
        assert ctk.check_task_owner_by_subtask(th.task_owner_key_id, subtask_id)
        assert not ctk.check_task_owner_by_subtask(th.task_owner_key_id, "!!!")
        assert not ctk.check_task_owner_by_subtask('???', subtask_id)
        subtask_id2 = generate_new_id_from_id(task_id)
        ctd2 = ComputeTaskDef()
        ctd2['task_id'] = task_id
        ctd2['subtask_id'] = subtask_id2
        ctk.receive_subtask(ctd2)
        assert ctk.active_tasks[task_id].requests == 0
        assert ctk.subtask_to_task.get(subtask_id2) is None
        assert ctk.subtask_to_task[subtask_id] == task_id
        ctk.active_tasks[task_id].requests = 1
        ctk.receive_subtask(ctd)
        assert ctk.active_tasks[task_id].requests == 1

    @mock.patch('golem.task.taskkeeper.CompTaskKeeper.dump')
    def test_get_task_env(self, dump_mock):
        ctk = CompTaskKeeper(Path('ignored'))
        with self.assertLogs(logger, level="WARNING"):
            assert ctk.get_task_env("task1") is None

        header = get_task_header()
        task_id1 = header.task_id
        ctk.add_request(header, 4002)

        header = get_task_header()
        task_id2 = header.task_id
        header.environment = "NOTDEFAULT"
        ctk.add_request(header, 4002)

        assert ctk.get_task_env(task_id2) == "NOTDEFAULT"
        assert ctk.get_task_env(task_id1) == "DEFAULT"

    def test_check_comp_task_def(self):
        ctk = CompTaskKeeper(self.new_path)
        header = get_task_header()
        task_id = header.task_id
        ctk.add_request(header, 40003)
        ctk.active_tasks[task_id].requests = 0
        subtask_id = generate_new_id_from_id(task_id)
        comp_task_def = {
            'task_id': task_id,
            'subtask_id': subtask_id,
            'deadline': get_timestamp_utc() + 100,
        }
        with self.assertLogs(logger, level="INFO") as l:
            assert not ctk.check_comp_task_def(comp_task_def)
        assert 'Cannot accept subtask %s for task %s. ' \
               'Request for this task was not send.' % (subtask_id, task_id)\
               in l.output[0]

        ctk.active_tasks[task_id].requests = 1
        comp_task_def['deadline'] = 0
        with self.assertLogs(logger, level="INFO") as l:
            assert not ctk.check_comp_task_def(comp_task_def)
        assert 'Cannot accept subtask %s for task %s. ' \
               'Request for this task has wrong deadline 0' % (subtask_id,
                                                               task_id) \
               in l.output[0]

        comp_task_def['deadline'] = get_timestamp_utc() + 240

        with self.assertLogs(logger, level="INFO"):
            assert not ctk.check_comp_task_def(comp_task_def)

        comp_task_def['deadline'] = get_timestamp_utc() + 100
        assert ctk.check_comp_task_def(comp_task_def)

        ctk.active_tasks[task_id].subtasks[subtask_id] = comp_task_def
        with self.assertLogs(logger, level="INFO") as l:
            assert not ctk.check_comp_task_def(comp_task_def)
        assert 'Cannot accept subtask %s for task %s. ' \
               'Definition of this subtask was already received.' % (subtask_id,
                                                                     task_id) \
               in l.output[0]

        del ctk.active_tasks[task_id].subtasks[subtask_id]
        assert ctk.check_comp_task_def(comp_task_def)
