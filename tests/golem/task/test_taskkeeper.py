# pylint: disable=protected-access
from datetime import timedelta
from pathlib import Path
import random
import time
import unittest.mock as mock

from eth_utils import encode_hex
from ethereum.utils import denoms
from freezegun import freeze_time
from golem_messages import idgenerator
from golem_messages import factories as msg_factories
from golem_messages.datastructures import tasks as dt_tasks
from golem_messages.datastructures.masking import Mask
from golem_messages.factories.datastructures import p2p as dt_p2p_factory
from golem_messages.message import ComputeTaskDef
from twisted.internet.defer import inlineCallbacks, Deferred
from twisted.trial.unittest import TestCase as TwistedTestCase

import golem
from golem.core import deferred as core_deferred
from golem.core.common import get_timestamp_utc, timeout_to_deadline
from golem.environments.environment import Environment, UnsupportReason,\
    SupportStatus
from golem.environments.environmentsmanager import \
    EnvironmentsManager as OldEnvManager
from golem.network.hyperdrive.client import HyperdriveClient
from golem.task.helpers import calculate_subtask_payment
from golem.task import taskarchiver
from golem.task import taskkeeper
from golem.task.envmanager import EnvironmentManager as NewEnvManager
from golem.task.taskkeeper import TaskHeaderKeeper, CompTaskKeeper, logger
from golem.testutils import PEP8MixIn
from golem.testutils import TempDirFixture
from golem.tools.assertlogs import LogTestCase


def async_run(request, success=None, error=None):
    try:
        result = request.method(*request.args, **request.kwargs)
    except Exception as exc:  # pylint: disable=broad-except
        if error:
            error(exc)
    else:
        if success:
            success(result)


class TestTaskHeaderKeeperIsSupported(TempDirFixture, LogTestCase):

    def setUp(self) -> None:
        super().setUp()
        self.tk = TaskHeaderKeeper(
            old_env_manager=OldEnvManager(),
            new_env_manager=NewEnvManager(self.new_path),
            node=dt_p2p_factory.Node(),
            min_price=10.0)
        self.tk.old_env_manager.environments = {}
        self.tk.old_env_manager.support_statuses = {}

    def _add_environment(self):
        e = Environment()
        e.accept_tasks = True
        self.tk.old_env_manager.add_environment(e)

    def test_supported(self):
        self._add_environment()
        header = get_task_header()
        header.max_price = 10.0
        self.assertTrue(self.tk.check_support(header))

    def test_header_uninitialized(self):
        header = get_task_header()
        header.environment = None
        header.max_price = None
        header.min_version = None
        self.assertFalse(core_deferred.sync_wait(self.tk.check_support(header)))

    def test_environment_missing(self):
        header = get_task_header()
        header.environment = Environment.get_id()
        supported = core_deferred.sync_wait(self.tk.check_support(header))
        self.assertFalse(supported)
        self.assertIn(UnsupportReason.ENVIRONMENT_MISSING, supported.desc)

    def test_max_price(self):
        self._add_environment()
        header = get_task_header()
        header.max_price = 0
        supported = core_deferred.sync_wait(self.tk.check_support(header))
        self.assertFalse(supported)
        self.assertIn(UnsupportReason.MAX_PRICE, supported.desc)

    def test_config_min_price(self):
        self._add_environment()
        header = get_task_header()
        header.max_price = 10.0

        config_desc = mock.Mock()
        config_desc.min_price = 13.0
        self.tk.change_config(config_desc)
        with self.assertLogs('golem.task.taskkeeper', level='INFO'):
            self.assertFalse(
                core_deferred.sync_wait(self.tk.check_support(header)),
            )

    def test_price_equal(self):
        self._add_environment()
        header = get_task_header()
        header.max_price = 10.0
        config_desc = mock.Mock()
        config_desc.min_price = 10.0
        self.tk.change_config(config_desc)
        self.assertTrue(self.tk.check_support(header))

    def test_mask_mismatch(self):
        self._add_environment()
        header = get_task_header()
        header.max_price = 10.0
        header.mask.matches = mock.Mock(return_value=False)

        with self.assertNoLogs('golem.task.taskkeeper', level='INFO'):
            supported = core_deferred.sync_wait(self.tk.check_support(header))

        self.assertFalse(supported)
        self.assertIn(UnsupportReason.MASK_MISMATCH, supported.desc)


class TaskHeaderKeeperBase(TempDirFixture, LogTestCase):
    def setUp(self):
        super().setUp()
        self.thk = taskkeeper.TaskHeaderKeeper(
            old_env_manager=OldEnvManager(),
            new_env_manager=NewEnvManager(self.new_path),
            node=dt_p2p_factory.Node(),
            min_price=10.0,
        )


class TestTaskHeaderKeeperWithArchiver(TaskHeaderKeeperBase):
    def setUp(self):
        super().setUp()
        self.tar = mock.Mock(spec=taskarchiver.TaskArchiver)
        self.thk = TaskHeaderKeeper(
            old_env_manager=OldEnvManager(),
            new_env_manager=NewEnvManager(self.new_path),
            node=dt_p2p_factory.Node(),
            min_price=10.0,
            task_archiver=self.tar,
        )

    def test_change_config(self):
        e = Environment()
        e.accept_tasks = True
        self.thk.old_env_manager.add_environment(e)

        task_header = get_task_header()
        task_id = task_header.task_id
        task_header.max_price = 9.0
        self.thk.add_task_header(task_header)
        self.assertNotIn(task_id, self.thk.supported_tasks)
        self.assertIn(task_id, self.thk.task_headers)

        task_header = get_task_header("abc")
        task_id2 = task_header.task_id
        task_header.max_price = 10.0
        self.thk.add_task_header(task_header)
        self.assertIn(task_id2, self.thk.supported_tasks)
        self.assertIn(task_id2, self.thk.task_headers)

        config_desc = mock.Mock()
        config_desc.min_price = 10.0
        self.thk.change_config(config_desc)
        self.assertNotIn(task_id, self.thk.supported_tasks)
        self.assertIn(task_id2, self.thk.supported_tasks)
        config_desc.min_price = 8.0
        self.thk.change_config(config_desc)
        self.assertIn(task_id, self.thk.supported_tasks)
        self.assertIn(task_id2, self.thk.supported_tasks)
        config_desc.min_price = 11.0
        self.thk.change_config(config_desc)
        self.assertNotIn(task_id, self.thk.supported_tasks)
        self.assertNotIn(task_id2, self.thk.supported_tasks)
        # Make sure the tasks stats are properly archived
        self.tar.reset_mock()
        config_desc.min_price = 9.5
        self.thk.change_config(config_desc)
        self.assertNotIn(task_id, self.thk.supported_tasks)
        self.assertIn(task_id2, self.thk.supported_tasks)
        self.tar.add_support_status.assert_any_call(
            task_id, SupportStatus(False, {UnsupportReason.MAX_PRICE: 9.0}))
        self.tar.add_support_status.assert_any_call(
            task_id2, SupportStatus(True, {}))

    def test_task_header_update_stats(self):
        e = Environment()
        e.accept_tasks = True
        self.thk.old_env_manager.add_environment(e)
        task_header = get_task_header("good")
        assert self.thk.add_task_header(task_header)
        self.tar.add_task.assert_called_with(mock.ANY)
        task_id = task_header.task_id
        self.tar.add_support_status.assert_any_call(
            task_id, SupportStatus(True, {}))

        self.tar.reset_mock()
        task_header2 = get_task_header("bad")
        task_id2 = task_header2.task_id
        task_header2.max_price = 1.0
        assert self.thk.add_task_header(task_header2)
        self.tar.add_task.assert_called_with(mock.ANY)
        self.tar.add_support_status.assert_any_call(
            task_id2, SupportStatus(False, {UnsupportReason.MAX_PRICE: 1.0}))


class TestTaskHeaderKeeper(TaskHeaderKeeperBase):
    def test_get_task(self):
        old_env_manager = OldEnvManager()
        # This is necessary because OldEnvManager is a singleton
        old_env_manager.environments = {}
        old_env_manager.support_statuses = {}

        self.assertIsNone(self.thk.get_task())
        task_header = get_task_header("uvw")
        self.assertTrue(self.thk.add_task_header(task_header))
        self.assertIsNone(self.thk.get_task())
        e = Environment()
        e.accept_tasks = True
        self.thk.old_env_manager.add_environment(e)
        task_header2 = get_task_header("xyz")
        self.assertTrue(self.thk.add_task_header(task_header2))
        th = self.thk.get_task()
        self.assertEqual(task_header2.to_dict(), th.to_dict())

    @freeze_time(as_arg=True)
    def test_old_tasks(frozen_time, self):  # pylint: disable=no-self-argument
        e = Environment()
        e.accept_tasks = True
        self.thk.old_env_manager.add_environment(e)
        task_header = get_task_header()
        task_header.deadline = timeout_to_deadline(10)
        assert self.thk.add_task_header(task_header)

        task_id = task_header.task_id
        task_header2 = get_task_header("abc")
        task_header2.deadline = timeout_to_deadline(1)
        task_id2 = task_header2.task_id
        assert self.thk.add_task_header(task_header2)
        assert self.thk.task_headers.get(task_id2) is not None
        assert self.thk.task_headers.get(task_id) is not None
        assert self.thk.removed_tasks.get(task_id2) is None
        assert self.thk.removed_tasks.get(task_id) is None
        assert len(self.thk.supported_tasks) == 2

        frozen_time.tick(timedelta(seconds=1.1))  # pylint: disable=no-member
        self.thk.remove_old_tasks()
        assert self.thk.task_headers.get(task_id2) is None
        assert self.thk.task_headers.get(task_id) is not None
        assert self.thk.removed_tasks.get(task_id2) is not None
        assert self.thk.removed_tasks.get(task_id) is None
        assert len(self.thk.supported_tasks) == 1
        assert self.thk.supported_tasks[0] == task_id

    @freeze_time(as_arg=True)
    def test_task_limit(frozen_time, self):  # pylint: disable=no-self-argument
        limit = self.thk.max_tasks_per_requestor

        thd = get_task_header("ta")
        thd.deadline = timeout_to_deadline(0.1)
        self.thk.add_task_header(thd)

        ids = [thd.task_id]
        for i in range(1, limit):
            thd = get_task_header("ta")
            ids.append(thd.task_id)
            self.thk.add_task_header(thd)

        for id_ in ids:
            self.assertIn(id_, self.thk.task_headers)

        thd = get_task_header("tb0")
        tb_id = thd.task_id
        self.thk.add_task_header(thd)

        for id_ in ids:
            self.assertIn(id_, self.thk.task_headers)

        self.assertIn(tb_id, self.thk.task_headers)

        frozen_time.tick(timedelta(seconds=0.1))  # pylint: disable=no-member

        thd = get_task_header("ta")
        new_task_id = thd.task_id
        self.thk.add_task_header(thd)
        self.assertNotIn(new_task_id, self.thk.task_headers)

        for id_ in ids:
            self.assertIn(id_, self.thk.task_headers)
        self.assertIn(tb_id, self.thk.task_headers)

        frozen_time.tick(timedelta(seconds=0.1))  # pylint: disable=no-member
        self.thk.remove_old_tasks()

        thd = get_task_header("ta")
        new_task_id = thd.task_id
        self.thk.add_task_header(thd)
        self.assertIn(new_task_id, self.thk.task_headers)

        self.assertNotIn(ids[0], self.thk.task_headers)
        for i in range(1, limit):
            self.assertIn(ids[i], self.thk.task_headers)
        self.assertIn(tb_id, self.thk.task_headers)

    @freeze_time(as_arg=True)
    # pylint: disable=no-self-argument
    def test_check_max_tasks_per_owner(freezer, self):

        tk = TaskHeaderKeeper(
            old_env_manager=OldEnvManager(),
            new_env_manager=NewEnvManager(self.new_path),
            node=dt_p2p_factory.Node(),
            min_price=10,
            max_tasks_per_requestor=10)
        limit = tk.max_tasks_per_requestor
        new_limit = 3

        ids = []
        for _ in range(new_limit):
            thd = get_task_header("ta")
            ids.append(thd.task_id)
            tk.add_task_header(thd)

            freezer.tick(timedelta(seconds=0.1))  # pylint: disable=no-member

        thd = get_task_header("tb0")
        tb0_id = thd.task_id
        tk.add_task_header(thd)

        freezer.tick(timedelta(seconds=0.1))  # pylint: disable=no-member

        def _assert_headers(ids_, len_):
            ids_.append(tb0_id)
            for id_ in ids_:
                self.assertIn(id_, tk.task_headers)
            self.assertEqual(len_, len(tk.task_headers))

        _assert_headers(ids, len(ids) + 1)

        new_ids = []
        for _ in range(new_limit, limit):
            thd = get_task_header("ta")
            new_ids.append(thd.task_id)
            tk.add_task_header(thd)

            freezer.tick(timedelta(seconds=0.1))  # pylint: disable=no-member

        _assert_headers(ids + new_ids, limit + 1)

        # shouldn't remove any tasks
        tk.check_max_tasks_per_owner(thd.task_owner.key)

        _assert_headers(ids + new_ids, limit + 1)

        # Test if it skips a running task
        running_task_id = ids[0]
        tk.task_started(running_task_id)
        assert running_task_id in tk.running_tasks
        tk.max_tasks_per_requestor = tk.max_tasks_per_requestor - 1
        # shouldn't remove any tasks
        tk.check_max_tasks_per_owner(thd.task_owner.key)

        _assert_headers(ids + new_ids, limit + 1)

        # finish the task, restore state
        tk.task_ended(running_task_id)
        assert running_task_id not in tk.running_tasks

        tk.max_tasks_per_requestor = new_limit

        # should remove ta{3..9}
        tk.check_max_tasks_per_owner(thd.task_owner.key)

        _assert_headers(ids, new_limit + 1)

        # Test if it skips a running task
        running_task_id = ids[2]
        tk.task_started(running_task_id)
        assert running_task_id in tk.running_tasks
        tk.max_tasks_per_requestor = 1
        # shouldn't remove running_task_id
        tk.check_max_tasks_per_owner(thd.task_owner.key)

        # Should keep 0 and 2, since 2 is running
        _assert_headers([ids[0], ids[2]], 3)

        # finish the task, restore state
        tk.task_ended(running_task_id)
        assert running_task_id not in tk.running_tasks

    def test_get_unsupport_reasons(self):
        e = Environment()
        e.accept_tasks = True
        self.thk.old_env_manager.add_environment(e)

        # Supported task
        thd = get_task_header("good")
        self.thk.add_task_header(thd)

        # Wrong version
        thd = get_task_header("wrong version")
        thd.min_version = "42.0.17"
        self.thk.add_task_header(thd)

        # Wrong environment
        thd = get_task_header("wrong env")
        thd.environment = "UNKNOWN"
        self.thk.add_task_header(thd)

        # Wrong price
        thd = get_task_header("wrong price")
        thd.max_price = 1
        self.thk.add_task_header(thd)

        # Wrong price and version
        thd = get_task_header("wrong price and version")
        thd.min_version = "42.0.17"
        thd.max_price = 1
        self.thk.add_task_header(thd)

        # And one more with wrong version
        thd = get_task_header("wrong version 2")
        thd.min_version = "42.0.44"
        self.thk.add_task_header(thd)

        reasons = self.thk.get_unsupport_reasons()
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
        header = get_task_header()
        owner = header.task_owner.key
        key_id = header.task_id
        self.thk.add_task_header(header)
        assert self.thk.get_owner(key_id) == owner
        assert self.thk.get_owner("UNKNOWN") is None


class TestTHKTaskEnded(TaskHeaderKeeperBase):
    def test_task_not_found(self):
        task_id = 'non existent id'
        self.assertNotIn(task_id, self.thk.running_tasks)
        self.thk.task_ended(task_id)


def get_dict_task_header(key_id_seed="kkk"):
    key_id = str.encode(key_id_seed)
    return {
        "task_id": idgenerator.generate_id(key_id),
        "task_owner": {
            "node_name": "Bob's node",
            "key": encode_hex(key_id)[2:],
            "pub_addr": "10.10.10.10",
            "pub_port": 10101
        },
        "environment": "DEFAULT",
        "deadline": timeout_to_deadline(1201),
        "subtask_timeout": 120,
        "subtasks_count": 1,
        "max_price": 10,
        "min_version": golem.__version__,
        "estimated_memory": 0,
        'mask': Mask().to_bytes(),
        'timestamp': 0,
        'signature': None
    }


def get_task_header(key_id_seed="kkk", **kwargs):
    th_dict_repr = get_dict_task_header(key_id_seed=key_id_seed)
    th_dict_repr.update(kwargs)
    return dt_tasks.TaskHeader(**th_dict_repr)


@mock.patch('golem.task.taskkeeper.ProviderStatsManager', mock.Mock())
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
        for _ in range(10):
            header = get_task_header()
            header.deadline = timeout_to_deadline(1)
            header.subtask_timeout = 3

            test_headers.append(header)
            price = calculate_subtask_payment(
                int(random.random() * 100),
                header.subtask_timeout,
            )
            ctk.add_request(header, price, 0.0, 1)

            ctd = ComputeTaskDef()
            ctd['task_id'] = header.task_id
            ctd['subtask_id'] = idgenerator.generate_new_id_from_id(
                header.task_id,
            )
            ctd['deadline'] = timeout_to_deadline(header.subtask_timeout - 1)
            ttc = msg_factories.tasks.TaskToComputeFactory(
                price=price,
                size=1024
            )
            ttc.compute_task_def = ctd
            ttc.resources_options = {
                'client_id': HyperdriveClient.CLIENT_ID,
                'version': HyperdriveClient.VERSION,
                'options': {}
            }
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
        timestamp.return_value = int(time.time())
        tasks_dir = Path(self.path)
        self._dump_some_tasks(tasks_dir)

        ctk = CompTaskKeeper(tasks_dir)
        ctk.remove_old_tasks()

        self.assertTrue(any(ctk.active_tasks))
        self.assertTrue(any(ctk.subtask_to_task))
        timestamp.return_value = int(time.time() + 1)
        ctk.remove_old_tasks()
        self.assertTrue(any(ctk.active_tasks))
        self.assertTrue(any(ctk.subtask_to_task))
        timestamp.return_value = int(time.time() + 300)
        ctk.remove_old_tasks()
        self.assertTrue(not any(ctk.active_tasks))
        self.assertTrue(not any(ctk.subtask_to_task))

    @mock.patch('golem.task.taskkeeper.CompTaskKeeper.dump', mock.Mock())
    def test_comp_keeper(self):
        ctk = CompTaskKeeper(Path('ignored'))
        header = get_task_header()
        header.task_id = "xyz"
        header.subtask_timeout = 1

        with self.assertRaises(TypeError):
            ctk.add_request(header, "not a number", 0.0, 1)
        with self.assertRaises(ValueError):
            ctk.add_request(header, -2, 0.0, 1)

        budget = 5 * denoms.ether
        ctk.add_request(header, budget, 0.0, 1)
        self.assertEqual(ctk.active_tasks["xyz"].requests, 1)
        self.assertEqual(ctk.active_task_offers["xyz"], budget)
        self.assertEqual(ctk.active_tasks["xyz"].header, header)
        budget = 0.1 * denoms.ether
        ctk.add_request(header, budget, 0.0, 1)
        self.assertEqual(ctk.active_tasks["xyz"].requests, 2)
        self.assertEqual(ctk.active_task_offers["xyz"], budget)
        self.assertEqual(ctk.active_tasks["xyz"].header, header)
        header.task_id = "xyz2"
        budget = 314 * denoms.finney
        ctk.add_request(header, budget, 0.0, 1)
        self.assertEqual(ctk.active_task_offers["xyz2"], budget)
        header.task_id = "xyz"
        thread = get_task_header()
        thread.task_id = "qaz123WSX"
        with self.assertRaises(ValueError):
            ctk.add_request(thread, -1, 0.0, 1)
        with self.assertRaises(TypeError):
            ctk.add_request(thread, '1', 0.0, 1)
        ctk.add_request(thread, 12, 0.0, 1)

        ctd = ComputeTaskDef()
        ttc = msg_factories.tasks.TaskToComputeFactory(price=0)
        ttc.compute_task_def = ctd
        with self.assertLogs(logger, level="WARNING"):
            self.assertFalse(ctk.receive_subtask(ttc))
        with self.assertLogs(logger, level="WARNING"):
            self.assertIsNone(ctk.get_node_for_task_id("abc"))

        with self.assertLogs(logger, level="WARNING"):
            ctk.request_failure("abc")
        ctk.request_failure("xyz")
        self.assertEqual(ctk.active_tasks["xyz"].requests, 1)

    def test_receive_subtask_problems(self):
        ctk = CompTaskKeeper(Path(self.path))
        th = get_task_header()
        task_id = th.task_id
        price = calculate_subtask_payment(
            int(random.random() * 100),
            th.subtask_timeout,
        )
        ctk.add_request(th, price, 0.0, 1)
        subtask_id = idgenerator.generate_new_id_from_id(task_id)
        ctd = ComputeTaskDef()
        ctd['task_id'] = task_id
        ctd['subtask_id'] = subtask_id
        ctd['deadline'] = timeout_to_deadline(th.subtask_timeout - 1)
        ttc = msg_factories.tasks.TaskToComputeFactory(price=price)
        ttc.compute_task_def = ctd
        self.assertTrue(ctk.receive_subtask(ttc))
        assert ctk.active_tasks[task_id].requests == 0
        assert ctk.subtask_to_task[subtask_id] == task_id
        assert ctk.check_task_owner_by_subtask(th.task_owner.key, subtask_id)
        assert not ctk.check_task_owner_by_subtask(th.task_owner.key, "!!!")
        assert not ctk.check_task_owner_by_subtask('???', subtask_id)
        subtask_id2 = idgenerator.generate_new_id_from_id(task_id)
        ctd2 = ComputeTaskDef()
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

    def test_check_comp_task_def(self):
        ctk = CompTaskKeeper(self.new_path)
        header = get_task_header()
        task_id = header.task_id
        ctk.add_request(header, 40003, 0.0, 1)
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
               'Request for this task was not sent.' % (subtask_id, task_id)\
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


class TestTaskHeaderKeeperBase(TwistedTestCase):

    def setUp(self) -> None:
        super().setUp()
        self.old_env_manager = mock.Mock(spec=OldEnvManager)
        self.new_env_manager = mock.Mock(spec=NewEnvManager)
        self.keeper = TaskHeaderKeeper(
            old_env_manager=self.old_env_manager,
            new_env_manager=self.new_env_manager,
            node=dt_p2p_factory.Node()
        )

    def _patch_keeper(self, method):
        patch = mock.patch(f'golem.task.taskkeeper.TaskHeaderKeeper.{method}')
        self.addCleanup(patch.stop)
        return patch.start()


class TestCheckSupport(TestTaskHeaderKeeperBase):

    def setUp(self) -> None:
        super().setUp()
        self.check_new_env = self._patch_keeper('_check_new_environment')
        self.check_old_env = self._patch_keeper('_check_old_environment')
        self.check_mask = self._patch_keeper('check_mask')
        self.check_price = self._patch_keeper('check_price')

    @inlineCallbacks
    def test_new_env_unsupported(self):
        # Given
        status = SupportStatus.err({
            UnsupportReason.ENVIRONMENT_UNSUPPORTED: 'test_env'
        })
        self.check_new_env.return_value = Deferred()
        self.check_new_env.return_value.callback(status)
        self.check_mask.return_value = SupportStatus.ok()
        self.check_price.return_value = SupportStatus.ok()

        # When
        header = get_task_header(
            environment="test_env",
            environment_prerequisites={'key': 'value'}
        )
        result = yield self.keeper.check_support(header)

        # Then
        self.assertEqual(result, status)
        self.check_new_env.assert_called_once_with(
            header.environment, header.environment_prerequisites)
        self.check_old_env.assert_not_called()
        self.check_mask.assert_called_once_with(header)
        self.check_price.assert_called_once_with(header)

    @inlineCallbacks
    def test_new_env_ok(self):
        # Given
        status = SupportStatus.ok()
        self.check_new_env.return_value = Deferred()
        self.check_new_env.return_value.callback(status)
        self.check_mask.return_value = SupportStatus.ok()
        self.check_price.return_value = SupportStatus.ok()

        # When
        header = get_task_header(
            environment="test_env",
            environment_prerequisites={'key': 'value'}
        )
        result = yield self.keeper.check_support(header)

        # Then
        self.assertEqual(result, status)
        self.check_new_env.assert_called_once_with(
            header.environment, header.environment_prerequisites)
        self.check_old_env.assert_not_called()
        self.check_mask.assert_called_once_with(header)
        self.check_price.assert_called_once_with(header)

    @inlineCallbacks
    def test_old_env_unsupported(self):
        # Given
        status = SupportStatus.err({
            UnsupportReason.ENVIRONMENT_UNSUPPORTED: 'test_env'
        })
        self.check_old_env.return_value = status
        self.check_mask.return_value = SupportStatus.ok()
        self.check_price.return_value = SupportStatus.ok()

        # When
        header = get_task_header(environment="test_env")
        result = yield self.keeper.check_support(header)

        # Then
        self.assertEqual(result, status)
        self.check_new_env.assert_not_called()
        self.check_old_env.assert_called_once_with(header.environment)
        self.check_mask.assert_called_once_with(header)
        self.check_price.assert_called_once_with(header)

    @inlineCallbacks
    def test_old_env_ok(self):
        # Given
        status = SupportStatus.ok()
        self.check_old_env.return_value = status
        self.check_mask.return_value = SupportStatus.ok()
        self.check_price.return_value = SupportStatus.ok()

        # When
        header = get_task_header(environment="test_env")
        result = yield self.keeper.check_support(header)

        # Then
        self.assertEqual(result, status)
        self.check_new_env.assert_not_called()
        self.check_old_env.assert_called_once_with(header.environment)
        self.check_mask.assert_called_once_with(header)
        self.check_price.assert_called_once_with(header)

    @inlineCallbacks
    def test_mask_mismatch(self):
        # Given
        status = SupportStatus.err({
            UnsupportReason.MASK_MISMATCH: '0xdeadbeef'
        })
        self.check_old_env.return_value = SupportStatus.ok()
        self.check_mask.return_value = status
        self.check_price.return_value = SupportStatus.ok()

        # When
        header = get_task_header(environment="test_env")
        result = yield self.keeper.check_support(header)

        # Then
        self.assertEqual(result, status)
        self.check_new_env.assert_not_called()
        self.check_old_env.assert_called_once_with(header.environment)
        self.check_mask.assert_called_once_with(header)
        self.check_price.assert_called_once_with(header)

    @inlineCallbacks
    def test_price_too_low(self):
        # Given
        status = SupportStatus.err({
            UnsupportReason.MAX_PRICE: 10
        })
        self.check_old_env.return_value = SupportStatus.ok()
        self.check_mask.return_value = SupportStatus.ok()
        self.check_price.return_value = status

        # When
        header = get_task_header(environment="test_env")
        result = yield self.keeper.check_support(header)

        # Then
        self.assertEqual(result, status)
        self.check_new_env.assert_not_called()
        self.check_old_env.assert_called_once_with(header.environment)
        self.check_mask.assert_called_once_with(header)
        self.check_price.assert_called_once_with(header)

    @inlineCallbacks
    def test_all_wrong(self):
        # Given
        env_status = SupportStatus.err({
            UnsupportReason.ENVIRONMENT_MISSING: "test_env"
        })
        mask_status = SupportStatus.err({
            UnsupportReason.MASK_MISMATCH: '0xdeadbeef'
        })
        price_status = SupportStatus.err({
            UnsupportReason.MAX_PRICE: 10
        })
        self.check_old_env.return_value = env_status
        self.check_mask.return_value = mask_status
        self.check_price.return_value = price_status

        # When
        header = get_task_header(environment="new_env")
        result = yield self.keeper.check_support(header)

        # Then
        self.assertEqual(
            result, env_status.join(mask_status).join(price_status))
        self.check_new_env.assert_not_called()
        self.check_old_env.assert_called_once_with(header.environment)
        self.check_mask.assert_called_once_with(header)
        self.check_price.assert_called_once_with(header)


class TestCheckOldEnvironment(TestTaskHeaderKeeperBase):

    def test_ok(self):
        # Given
        self.old_env_manager.accept_tasks.return_value = True
        self.old_env_manager.get_support_status.return_value = \
            SupportStatus.ok()

        # When
        env_id = "test_env"
        result = self.keeper._check_old_environment(env_id)

        # Then
        self.assertEqual(result, SupportStatus.ok())
        self.old_env_manager.accept_tasks.assert_called_once_with(env_id)
        self.old_env_manager.get_support_status.assert_called_once_with(env_id)

    def test_not_accepting_tasks(self):
        # Given
        self.old_env_manager.accept_tasks.return_value = False
        self.old_env_manager.get_support_status.return_value = \
            SupportStatus.ok()

        # When
        env_id = "test_env"
        result = self.keeper._check_old_environment(env_id)

        # Then
        self.assertEqual(result, SupportStatus.err({
            UnsupportReason.ENVIRONMENT_NOT_ACCEPTING_TASKS: env_id
        }))
        self.old_env_manager.accept_tasks.assert_called_once_with(env_id)
        self.old_env_manager.get_support_status.assert_called_once_with(env_id)

    def test_env_unsupported(self):
        # Given
        env_id = "test_env"
        status = SupportStatus.err({
            UnsupportReason.ENVIRONMENT_UNSUPPORTED: env_id
        })
        self.old_env_manager.accept_tasks.return_value = True
        self.old_env_manager.get_support_status.return_value = status

        # When
        result = self.keeper._check_old_environment(env_id)

        # Then
        self.assertEqual(result, status)
        self.old_env_manager.accept_tasks.assert_called_once_with(env_id)
        self.old_env_manager.get_support_status.assert_called_once_with(env_id)

    def test_env_unsupported_and_not_accepting_tasks(self):
        # Given
        env_id = "test_env"
        status = SupportStatus.err({
            UnsupportReason.ENVIRONMENT_UNSUPPORTED: env_id
        })
        self.old_env_manager.accept_tasks.return_value = False
        self.old_env_manager.get_support_status.return_value = status

        # When
        result = self.keeper._check_old_environment(env_id)

        # Then
        self.assertEqual(result, status.join(SupportStatus.err({
            UnsupportReason.ENVIRONMENT_NOT_ACCEPTING_TASKS: env_id
        })))
        self.old_env_manager.accept_tasks.assert_called_once_with(env_id)
        self.old_env_manager.get_support_status.assert_called_once_with(env_id)


class TestCheckNewEnvironment(TestTaskHeaderKeeperBase):

    @inlineCallbacks
    def test_env_missing(self):
        # Given
        self.new_env_manager.environment.side_effect = KeyError("test")

        # When
        env_id = "test_env"
        result = yield self.keeper._check_new_environment(env_id, {})

        # Then
        self.assertEqual(result, SupportStatus.err({
            UnsupportReason.ENVIRONMENT_MISSING: env_id
        }))
        self.new_env_manager.environment.assert_called_once_with(env_id)

    @inlineCallbacks
    def test_prerequisites_parsing_error(self):
        # Given
        env = self.new_env_manager.environment.return_value
        env.parse_prerequisites.side_effect = ValueError("test")

        # When
        env_id = "test_env"
        prereqs_dict = {"key": "value"}
        result = yield self.keeper._check_new_environment(env_id, prereqs_dict)

        # Then
        self.assertEqual(result, SupportStatus.err({
            UnsupportReason.ENVIRONMENT_UNSUPPORTED: env_id
        }))
        self.new_env_manager.environment.assert_called_once_with(env_id)
        env.parse_prerequisites.assert_called_once_with(prereqs_dict)
        env.install_prerequisites.assert_not_called()

    @inlineCallbacks
    def test_prerequisites_installation_error(self):
        # Given
        install_result = Deferred()
        install_result.callback(False)  # False means installation failed
        env = self.new_env_manager.environment.return_value
        env.install_prerequisites.return_value = install_result

        # When
        env_id = "test_env"
        prereqs_dict = {"key": "value"}
        result = yield self.keeper._check_new_environment(env_id, prereqs_dict)

        # Then
        self.assertEqual(result, SupportStatus.err({
            UnsupportReason.ENVIRONMENT_UNSUPPORTED: env_id
        }))
        self.new_env_manager.environment.assert_called_once_with(env_id)
        env.parse_prerequisites.assert_called_once_with(prereqs_dict)
        env.install_prerequisites.assert_called_once_with(
            env.parse_prerequisites())

    @inlineCallbacks
    def test_ok(self):
        # Given
        install_result = Deferred()
        install_result.callback(True)  # True means installation succeeded
        env = self.new_env_manager.environment.return_value
        env.install_prerequisites.return_value = install_result

        # When
        env_id = "test_env"
        prereqs_dict = {"key": "value"}
        result = yield self.keeper._check_new_environment(env_id, prereqs_dict)

        # Then
        self.assertEqual(result, SupportStatus.ok())
        self.new_env_manager.environment.assert_called_once_with(env_id)
        env.parse_prerequisites.assert_called_once_with(prereqs_dict)
        env.install_prerequisites.assert_called_once_with(
            env.parse_prerequisites())
