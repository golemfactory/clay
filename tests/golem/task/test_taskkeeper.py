import copy
from datetime import timedelta
from pathlib import Path
import random
import time
from unittest import TestCase
import unittest.mock as mock

from eth_utils import encode_hex
from freezegun import freeze_time
from golem_messages import idgenerator
from golem_messages import factories as msg_factories
from golem_messages.message import ComputeTaskDef

import golem
from golem.core.common import get_timestamp_utc, timeout_to_deadline
from golem.environments.environment import Environment, UnsupportReason,\
    SupportStatus
from golem.environments.environmentsmanager import EnvironmentsManager
from golem.network.p2p.node import Node
from golem.task import taskkeeper
from golem.task.masking import Mask
from golem.task.taskbase import TaskHeader
from golem.task.taskkeeper import TaskHeaderKeeper, CompTaskKeeper,\
    CompSubtaskInfo, logger
from golem.testutils import PEP8MixIn
from golem.testutils import TempDirFixture
from golem.tools.assertlogs import LogTestCase

from tests.factories import p2p


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
        tk = TaskHeaderKeeper(
            environments_manager=EnvironmentsManager(),
            node=p2p.Node(),
            min_price=10.0)
        self.assertIsInstance(tk, TaskHeaderKeeper)

    def test_is_supported(self):
        em = EnvironmentsManager()
        em.environments = {}
        em.support_statuses = {}

        tk = TaskHeaderKeeper(
            environments_manager=EnvironmentsManager(),
            node=p2p.Node(),
            min_price=10.0)

        header = get_task_header()
        header.fixed_header.environment = None
        header.fixed_header.max_price = None
        header.fixed_header.min_version = None
        self.assertFalse(tk.check_support(header))

        header.fixed_header.environment = Environment.get_id()
        header.fixed_header.max_price = 0
        supported = tk.check_support(header)
        self.assertFalse(supported)
        self.assertIn(UnsupportReason.ENVIRONMENT_MISSING, supported.desc)

        e = Environment()
        e.accept_tasks = True
        tk.environments_manager.add_environment(e)
        supported = tk.check_support(header)
        self.assertFalse(supported)
        self.assertIn(UnsupportReason.MAX_PRICE, supported.desc)

        header.fixed_header.max_price = 10.0
        supported = tk.check_support(header)
        self.assertFalse(supported)
        self.assertIn(UnsupportReason.APP_VERSION, supported.desc)

        header.fixed_header.min_version = golem.__version__
        self.assertTrue(tk.check_support(header))

        header.fixed_header.max_price = 10.0
        self.assertTrue(tk.check_support(header))

        config_desc = mock.Mock()
        config_desc.min_price = 13.0
        tk.change_config(config_desc)
        self.assertFalse(tk.check_support(header))

        config_desc.min_price = 10.0
        tk.change_config(config_desc)
        self.assertTrue(tk.check_support(header))

        header.fixed_header.min_version = "120"
        self.assertFalse(tk.check_support(header))

        header.fixed_header.min_version = tk.app_version
        self.assertTrue(tk.check_support(header))

        header.fixed_header.min_version = "abc"
        with self.assertLogs(logger=logger, level='WARNING'):
            self.assertFalse(tk.check_support(header))

    def test_check_version_compatibility(self):
        tk = TaskHeaderKeeper(
            environments_manager=EnvironmentsManager(),
            node=p2p.Node(),
            min_price=10.0)
        tk.app_version = '0.4.5-dev+232.138018'

        for v in ['', '0', '1.5', '0.4-alpha+build.2004.01.01', '0.4-alpha']:
            with self.assertRaises(ValueError, msg=v):
                tk.check_version_compatibility(v)

        for v in ['1.5.0', '1.4.0', '0.5.0', '0.3.0']:
            self.assertFalse(tk.check_version_compatibility(v), msg=v)

        for v in ['0.4.5', '0.4.1', '0.4.0', '0.4.0-alpha',
                  '0.4.0-alpha+build', '0.4.0-alpha+build.2010', '0.4.6']:
            self.assertTrue(tk.check_version_compatibility(v), msg=v)

    @mock.patch('golem.task.taskarchiver.TaskArchiver')
    def test_change_config(self, tar):
        tk = TaskHeaderKeeper(
            environments_manager=EnvironmentsManager(),
            node=p2p.Node(),
            min_price=10.0,
            task_archiver=tar)
        e = Environment()
        e.accept_tasks = True
        tk.environments_manager.add_environment(e)

        task_header = get_task_header()
        task_id = task_header.task_id
        task_header.fixed_header.max_price = 9.0
        tk.add_task_header(task_header)
        self.assertNotIn(task_id, tk.supported_tasks)
        self.assertIn(task_id, tk.task_headers)

        task_header = get_task_header("abc")
        task_id2 = task_header.task_id
        task_header.fixed_header.max_price = 10.0
        tk.add_task_header(task_header)
        self.assertIn(task_id2, tk.supported_tasks)
        self.assertIn(task_id2, tk.task_headers)

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
        em = EnvironmentsManager()
        em.environments = {}
        em.support_statuses = {}

        tk = TaskHeaderKeeper(
            environments_manager=em,
            node=p2p.Node(),
            min_price=10)

        self.assertIsNone(tk.get_task())
        task_header = get_task_header("uvw")
        self.assertTrue(tk.add_task_header(task_header))
        self.assertIsNone(tk.get_task())
        e = Environment()
        e.accept_tasks = True
        tk.environments_manager.add_environment(e)
        task_header2 = get_task_header("xyz")
        self.assertTrue(tk.add_task_header(task_header2))
        th = tk.get_task()
        assert isinstance(th.task_owner, Node)
        self.assertEqual(task_header2.to_dict(), th.to_dict())

    @freeze_time(as_arg=True)
    def test_old_tasks(frozen_time, _):  # pylint: disable=no-self-argument
        tk = TaskHeaderKeeper(
            environments_manager=EnvironmentsManager(),
            node=p2p.Node(),
            min_price=10)
        e = Environment()
        e.accept_tasks = True
        tk.environments_manager.add_environment(e)
        task_header = get_task_header()
        task_header.fixed_header.deadline = timeout_to_deadline(10)
        assert tk.add_task_header(task_header)

        task_id = task_header.task_id
        task_header2 = get_task_header("abc")
        task_header2.fixed_header.deadline = timeout_to_deadline(1)
        task_id2 = task_header2.task_id
        assert tk.add_task_header(task_header2)
        assert tk.task_headers.get(task_id2) is not None
        assert tk.task_headers.get(task_id) is not None
        assert tk.removed_tasks.get(task_id2) is None
        assert tk.removed_tasks.get(task_id) is None
        assert len(tk.supported_tasks) == 2

        frozen_time.tick(timedelta(seconds=1.1))  # pylint: disable=no-member
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

        tk = TaskHeaderKeeper(
            environments_manager=EnvironmentsManager(),
            node=p2p.Node(),
            min_price=10)
        tk.environments_manager.add_environment(e)

        task_header = get_task_header()
        task_id = task_header.task_id

        task_header.fixed_header.deadline = timeout_to_deadline(10)
        task_header.fixed_header.update_checksum()
        assert tk.add_task_header(task_header)
        assert task_id in tk.supported_tasks
        assert tk.add_task_header(task_header)
        assert task_id in tk.supported_tasks

        task_header = copy.deepcopy(task_header)
        task_header.fixed_header.max_price = 1
        task_header.fixed_header.update_checksum()
        # An attempt to update fixed header should *not* succeed
        assert not tk.add_task_header(task_header)
        assert task_id in tk.supported_tasks

        tk.task_headers = {}
        tk.supported_tasks = []

        assert tk.add_task_header(task_header)
        assert task_id not in tk.supported_tasks

    @mock.patch('golem.task.taskarchiver.TaskArchiver')
    def test_task_header_update_stats(self, tar):
        e = Environment()
        e.accept_tasks = True
        tk = TaskHeaderKeeper(
            environments_manager=EnvironmentsManager(),
            node=p2p.Node(),
            min_price=10,
            task_archiver=tar)
        tk.environments_manager.add_environment(e)
        task_header = get_task_header("good")
        assert tk.add_task_header(task_header)
        tar.add_task.assert_called_with(mock.ANY)
        task_id = task_header.task_id
        tar.add_support_status.assert_any_call(
            task_id, SupportStatus(True, {}))

        tar.reset_mock()
        task_header2 = get_task_header("bad")
        task_id2 = task_header2.task_id
        task_header2.fixed_header.max_price = 1.0
        assert tk.add_task_header(task_header2)
        tar.add_task.assert_called_with(mock.ANY)
        tar.add_support_status.assert_any_call(
            task_id2, SupportStatus(False, {UnsupportReason.MAX_PRICE: 1.0}))

    @freeze_time(as_arg=True)
    def test_task_limit(frozen_time, self):  # pylint: disable=no-self-argument
        tk = TaskHeaderKeeper(
            environments_manager=EnvironmentsManager(),
            node=p2p.Node(),
            min_price=10)
        limit = tk.max_tasks_per_requestor

        thd = get_task_header("ta")
        thd.fixed_header.deadline = timeout_to_deadline(0.1)
        tk.add_task_header(thd)

        ids = [thd.task_id]
        for i in range(1, limit):
            thd = get_task_header("ta")
            ids.append(thd.task_id)
            tk.add_task_header(thd)
        last_add_time = time.time()

        for id_ in ids:
            self.assertIn(id_, tk.task_headers)

        thd = get_task_header("tb0")
        tb_id = thd.task_id
        tk.add_task_header(thd)

        for id_ in ids:
            self.assertIn(id_, tk.task_headers)

        self.assertIn(tb_id, tk.task_headers)

        while time.time() == last_add_time:
            frozen_time.tick(  # pylint: disable=no-member
                delta=timedelta(milliseconds=100))

        thd = get_task_header("ta")
        new_task_id = thd.task_id
        tk.add_task_header(thd)
        self.assertNotIn(new_task_id, tk.task_headers)

        for id_ in ids:
            self.assertIn(id_, tk.task_headers)
        self.assertIn(tb_id, tk.task_headers)

        frozen_time.tick(  # pylint: disable=no-member
            delta=timedelta(milliseconds=100))
        tk.remove_old_tasks()

        thd = get_task_header("ta")
        new_task_id = thd.task_id
        tk.add_task_header(thd)
        self.assertIn(new_task_id, tk.task_headers)

        self.assertNotIn(ids[0], tk.task_headers)
        for i in range(1, limit):
            self.assertIn(ids[i], tk.task_headers)
        self.assertIn(tb_id, tk.task_headers)

    def test_check_max_tasks_per_owner(self):
        tk = TaskHeaderKeeper(
            environments_manager=EnvironmentsManager(),
            node=p2p.Node(),
            min_price=10,
            max_tasks_per_requestor=10)
        limit = tk.max_tasks_per_requestor
        new_limit = 3

        ids = []
        for i in range(new_limit):
            thd = get_task_header("ta")
            ids.append(thd.task_id)
            tk.add_task_header(thd)
        last_add_time = time.time()

        thd = get_task_header("tb0")
        tb0_id = thd.task_id
        tk.add_task_header(thd)

        for id_ in ids:
            self.assertIn(id_, tk.task_headers)
        self.assertIn(tb0_id, tk.task_headers)

        while time.time() == last_add_time:
            time.sleep(0.1)

        new_ids = []
        for i in range(new_limit, limit):
            thd = get_task_header("ta")
            new_ids.append(thd.task_id)
            tk.add_task_header(thd)

        for id_ in ids + new_ids:
            self.assertIn(id_, tk.task_headers)
        self.assertIn(tb0_id, tk.task_headers)
        self.assertEqual(limit + 1, len(tk.task_headers))

        # shouldn't remove any tasks
        tk.check_max_tasks_per_owner(thd.task_owner.key)

        for id_ in ids + new_ids:
            self.assertIn(id_, tk.task_headers)
        self.assertIn(tb0_id, tk.task_headers)
        self.assertEqual(limit + 1, len(tk.task_headers))

        tk.max_tasks_per_requestor = new_limit

        # should remove ta{3..9}
        tk.check_max_tasks_per_owner(thd.task_owner.key)

        for id_ in ids:
            self.assertIn(id_, tk.task_headers)
        self.assertIn(tb0_id, tk.task_headers)
        self.assertEqual(new_limit + 1, len(tk.task_headers))

    def test_get_unsupport_reasons(self):
        tk = TaskHeaderKeeper(
            environments_manager=EnvironmentsManager(),
            node=p2p.Node(),
            min_price=10)
        e = Environment()
        e.accept_tasks = True
        tk.environments_manager.add_environment(e)

        # Supported task
        thd = get_task_header("good")
        tk.add_task_header(thd)

        # Wrong version
        thd = get_task_header("wrong version")
        thd.fixed_header.min_version = "42.0.17"
        tk.add_task_header(thd)

        # Wrong environment
        thd = get_task_header("wrong env")
        thd.fixed_header.environment = "UNKNOWN"
        tk.add_task_header(thd)

        # Wrong price
        thd = get_task_header("wrong price")
        thd.fixed_header.max_price = 1
        tk.add_task_header(thd)

        # Wrong price and version
        thd = get_task_header("wrong price and version")
        thd.fixed_header.min_version = "42.0.17"
        thd.fixed_header.max_price = 1
        tk.add_task_header(thd)

        # And one more with wrong version
        thd = get_task_header("wrong version 2")
        thd.fixed_header.min_version = "42.0.44"
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
        tk = TaskHeaderKeeper(
            environments_manager=EnvironmentsManager(),
            node=p2p.Node(),
            min_price=10)
        header = get_task_header()
        owner = header.task_owner.key
        key_id = header.task_id
        tk.add_task_header(header)
        assert tk.get_owner(key_id) == owner
        assert tk.get_owner("UNKNOWN") is None


def get_dict_task_header(key_id_seed="kkk"):
    key_id = str.encode(key_id_seed)
    return {
        'fixed_header': {
            "task_id": idgenerator.generate_id(key_id),
            "task_owner": {
                "node_name": "Bob's node",
                "key": encode_hex(key_id)[2:],
                "pub_addr": "10.10.10.10",
                "pub_port": 10101
            },
            "environment": "DEFAULT",
            "last_checking": time.time(),
            "deadline": timeout_to_deadline(1201),
            "subtask_timeout": 120,
            "max_price": 10,
            "min_version": golem.__version__,
            "resource_size": 0,
            "estimated_memory": 0,
        },
        'mask': {
            'byte_repr': Mask().to_bytes()
        },
        'timestamp': 0,
        'signature': None
    }


def get_task_header(key_id_seed="kkk"):
    th_dict_repr = get_dict_task_header(key_id_seed=key_id_seed)
    return TaskHeader.from_dict(th_dict_repr)


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
            price_bid = int(random.random() * 100)
            ctk.add_request(header, price_bid)

            ctd = ComputeTaskDef(
                task_type='Blender',
                meta_parameters=msg_factories.tasks. \
                    BlenderScriptPackageFactory()
            )
            ctd['task_id'] = header.task_id
            ctd['subtask_id'] = idgenerator.generate_new_id_from_id(
                header.task_id,
            )
            ctd['deadline'] = timeout_to_deadline(header.subtask_timeout - 0.5)
            price = taskkeeper.compute_subtask_value(
                price_bid,
                header.subtask_timeout,
            )
            ttc = msg_factories.tasks.TaskToComputeFactory(price=price)
            ttc.compute_task_def = ctd
            self.assertTrue(ctk.receive_subtask(ttc))
            test_subtasks_ids.append(ctd['subtask_id'])
        del ctk

        another_ctk = CompTaskKeeper(tasks_dir)
        for (subtask_id, header) in zip(test_subtasks_ids, test_headers):
            self.assertIn(subtask_id, another_ctk.subtask_to_task)
            self.assertIn(header.task_id, another_ctk.active_tasks)

    @mock.patch('golem.core.golem_async.async_run', async_run)
    def test_persistence(self):
        """Tests whether tasks are persistent between restarts."""
        tasks_dir = Path(self.path)
        self._dump_some_tasks(tasks_dir)

    @mock.patch('golem.core.golem_async.async_run', async_run)
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
        self.assertEqual(ctk.get_value("xyz"), 240)
        header.task_id = "xyz2"
        ctk.add_request(header, 25000)
        self.assertEqual(ctk.active_tasks["xyz2"].price, 25000)
        self.assertEqual(ctk.get_value("xyz2"), 834)
        header.task_id = "xyz"
        thread = get_task_header()
        thread.task_id = "qaz123WSX"
        with self.assertRaises(ValueError):
            ctk.add_request(thread, -1)
        with self.assertRaises(TypeError):
            ctk.add_request(thread, '1')
        ctk.add_request(thread, 12)
        self.assertEqual(ctk.get_value(thread.task_id), 1)

        ctd = ComputeTaskDef(
            task_type='Blender',
            meta_parameters=msg_factories.tasks.BlenderScriptPackageFactory()
        )
        ttc = msg_factories.tasks.TaskToComputeFactory(price=0)
        ttc.compute_task_def = ctd
        with self.assertLogs(logger, level="WARNING"):
            self.assertFalse(ctk.receive_subtask(ttc))
        with self.assertLogs(logger, level="WARNING"):
            self.assertIsNone(ctk.get_node_for_task_id("abc"))
        with self.assertLogs(logger, level="WARNING"):
            self.assertIsNone(ctk.get_value("abc"))

        with self.assertLogs(logger, level="WARNING"):
            ctk.request_failure("abc")
        ctk.request_failure("xyz")
        self.assertEqual(ctk.active_tasks["xyz"].requests, 1)

    def test_receive_subtask_problems(self):
        ctk = CompTaskKeeper(Path(self.path), False)
        th = get_task_header()
        task_id = th.task_id
        price_bid = 5
        ctk.add_request(th, price_bid)
        subtask_id = idgenerator.generate_new_id_from_id(task_id)
        ctd = ComputeTaskDef(
            task_type='Blender',
            meta_parameters=msg_factories.tasks.BlenderScriptPackageFactory()
        )
        ctd['task_id'] = task_id
        ctd['subtask_id'] = subtask_id
        ctd['deadline'] = timeout_to_deadline(th.subtask_timeout - 1)
        price = taskkeeper.compute_subtask_value(
            price_bid,
            th.subtask_timeout,
        )
        ttc = msg_factories.tasks.TaskToComputeFactory(price=price)
        ttc.compute_task_def = ctd
        self.assertTrue(ctk.receive_subtask(ttc))
        assert ctk.active_tasks[task_id].requests == 0
        assert ctk.subtask_to_task[subtask_id] == task_id
        assert ctk.check_task_owner_by_subtask(th.task_owner.key, subtask_id)
        assert not ctk.check_task_owner_by_subtask(th.task_owner.key, "!!!")
        assert not ctk.check_task_owner_by_subtask('???', subtask_id)
        subtask_id2 = idgenerator.generate_new_id_from_id(task_id)
        ctd2 = ComputeTaskDef(
            task_type='Blender',
            meta_parameters=msg_factories.tasks.BlenderScriptPackageFactory()
        )
        ctd2['task_id'] = task_id
        ctd2['subtask_id'] = subtask_id2
        ttc.compute_task_def = ctd2
        self.assertFalse(ctk.receive_subtask(ttc))
        assert ctk.active_tasks[task_id].requests == 0
        assert ctk.subtask_to_task.get(subtask_id2) is None
        assert ctk.subtask_to_task[subtask_id] == task_id
        ctk.active_tasks[task_id].requests = 1
        ttc.compute_task_def = ctd
        self.assertFalse(ctk.receive_subtask(ttc))
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
        subtask_id = idgenerator.generate_new_id_from_id(task_id)
        comp_task_def = {
            'task_id': task_id,
            'subtask_id': subtask_id,
            'deadline': get_timestamp_utc() + 100,
        }
        with self.assertLogs(logger, level="INFO") as logs:
            assert not ctk.check_comp_task_def(comp_task_def)
        assert 'Cannot accept subtask %s for task %s. ' \
               'Request for this task was not send.' % (subtask_id, task_id)\
               in logs.output[0]

        ctk.active_tasks[task_id].requests = 1
        comp_task_def['deadline'] = 0
        with self.assertLogs(logger, level="INFO") as logs:
            assert not ctk.check_comp_task_def(comp_task_def)
        assert 'Cannot accept subtask %s for task %s. ' \
               'Request for this task has wrong deadline 0' % (subtask_id,
                                                               task_id) \
               in logs.output[0]

        comp_task_def['deadline'] = get_timestamp_utc() + 240

        with self.assertLogs(logger, level="INFO"):
            assert not ctk.check_comp_task_def(comp_task_def)

        comp_task_def['deadline'] = get_timestamp_utc() + 100
        assert ctk.check_comp_task_def(comp_task_def)

        ctk.active_tasks[task_id].subtasks[subtask_id] = comp_task_def
        with self.assertLogs(logger, level="INFO") as logs:
            assert not ctk.check_comp_task_def(comp_task_def)
        assert 'Cannot accept subtask %s for task %s. ' \
               'Definition of this subtask was already received.' % (subtask_id,
                                                                     task_id) \
               in logs.output[0]

        del ctk.active_tasks[task_id].subtasks[subtask_id]
        assert ctk.check_comp_task_def(comp_task_def)

        comp_task_def['subtask_id'] = "abc"
        with self.assertLogs(logger, level="INFO") as log_:
            assert not ctk.check_comp_task_def(comp_task_def)
        assert "Cannot accept subtask abc for task %s. " \
               "Subtask id was not generated from requestor's " \
               "key." % (task_id) in log_.output[0]

    def test_add_package_paths(self):
        ctk = CompTaskKeeper(self.new_path)
        task_id = 'veryimportanttask'
        package_paths = ['path/to/file']
        ctk.add_package_paths(task_id, package_paths)
        self.assertEqual(ctk.task_package_paths[task_id], package_paths)

    def test_get_package_paths(self):
        ctk = CompTaskKeeper(self.new_path)
        task_id = 'veryimportanttask'
        package_paths = ['path/to/file']
        ctk.task_package_paths[task_id] = package_paths
        self.assertEqual(ctk.get_package_paths(task_id), package_paths)

    def test_package_paths_restore(self):
        ctk = CompTaskKeeper(self.new_path)
        task_id = 'veryimportanttask'
        package_paths = ['path/to/file']
        ctk.add_package_paths(task_id, package_paths)
        ctk._dump_tasks()
        ctk.task_package_paths = {}
        ctk.restore()
        self.assertEqual(ctk.get_package_paths(task_id), package_paths)
