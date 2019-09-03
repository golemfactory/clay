import asyncio

from freezegun import freeze_time
from golem_task_api.client import RequestorAppClient
from golem_task_api.structs import Subtask
from mock import Mock, patch, MagicMock
import pytest
from twisted.internet.defer import inlineCallbacks
from twisted.trial.unittest import TestCase as TwistedTestCase

from golem.app_manager import AppManager
from golem.core.common import install_reactor
from golem.tools.testwithreactor import uninstall_reactor
from golem.core.deferred import deferred_from_future
from golem.model import default_now, RequestedTask, RequestedSubtask
from golem.task.envmanager import EnvironmentManager
from golem.task.requestedtaskmanager import (
    ComputingNode,
    CreateTaskParams,
    RequestedTaskManager,
    ComputingNodeDefinition,
)
from golem.task.taskstate import TaskStatus, SubtaskStatus
from golem.testutils import DatabaseFixture


class AsyncMock(MagicMock):
    async def __call__(self, *args, **kwargs):
        return super().__call__(*args, **kwargs)


class TestRequestedTaskManager(DatabaseFixture, TwistedTestCase):
    @classmethod
    def setUpClass(cls):
        try:
            uninstall_reactor()  # Because other tests don't clean up
        except AttributeError:
            pass
        cls.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(cls.loop)
        install_reactor()

    @classmethod
    def tearDownClass(cls) -> None:
        uninstall_reactor()
        asyncio.set_event_loop(None)

    def setUp(self):
        super().setUp()
        self.env_manager = Mock(spec=EnvironmentManager)
        self.app_manager = Mock(spec=AppManager)
        self.public_key = str.encode('0xdeadbeef')
        self.rtm = RequestedTaskManager(
            env_manager=self.env_manager,
            app_manager=self.app_manager,
            public_key=self.public_key,
            root_path=self.new_path
        )

    def tearDown(self):
        super().tearDown()

    def test_create_task(self):
        with freeze_time() as freezer:
            # given
            golem_params = self._build_golem_params()
            app_params = {}
            # when
            task_id = self.rtm.create_task(golem_params, app_params)
            freezer.tick()
            # then
            row = RequestedTask.get(RequestedTask.task_id == task_id)
            assert row.status == TaskStatus.creating
            assert row.start_time < default_now()
            assert (self.new_path / golem_params.app_id / task_id).exists()

    @inlineCallbacks
    def test_init_task(self):
        # given
        mock_client = self._mock_client_create()

        task_id = self._create_task()
        # when
        yield self._coro_to_def(self.rtm.init_task(task_id))
        row = RequestedTask.get(RequestedTask.task_id == task_id)
        # then
        assert row.status == TaskStatus.creating
        mock_client.create_task.assert_called_once_with(
            row.task_id,
            row.max_subtasks,
            row.app_params
        )
        self.app_manager.enabled.assert_called_once_with(row.app_id)

    @inlineCallbacks
    def test_init_task_wrong_status(self):
        # given
        self._mock_client_create()

        task_id = self._create_task()
        # when
        yield self._coro_to_def(self.rtm.init_task(task_id))
        # Start task to change the status
        self.rtm.start_task(task_id)
        # then
        with pytest.raises(RuntimeError):
            yield self._coro_to_def(self.rtm.init_task(task_id))

    @inlineCallbacks
    def test_start_task(self):
        # given
        self._mock_client_create()

        task_id = self._create_task()
        yield self._coro_to_def(self.rtm.init_task(task_id))
        # when
        self.rtm.start_task(task_id)
        # then
        row = RequestedTask.get(RequestedTask.task_id == task_id)
        assert row.status == TaskStatus.waiting

    def test_task_exists(self):
        task_id = self._create_task()
        self.assertTrue(self.rtm.task_exists(task_id))

    def test_task_not_exists(self):
        task_id = 'a'
        self.assertFalse(self.rtm.task_exists(task_id))

    @inlineCallbacks
    def test_has_pending_subtasks(self):
        # given
        mock_client = self._mock_client_create()
        mock_client.has_pending_subtasks.return_value = True

        task_id = self._create_task()
        yield self._coro_to_def(self.rtm.init_task(task_id))
        self.rtm.start_task(task_id)
        # when
        res = yield self._coro_to_def(self.rtm.has_pending_subtasks(task_id))
        # then
        self.assertTrue(res)
        mock_client.has_pending_subtasks.assert_called_once_with(task_id)

    @inlineCallbacks
    def test_get_next_subtask(self):
        # given
        mock_client = self._mock_client_create()
        self._add_next_subtask_to_client_mock(mock_client)

        task_id = self._create_task()
        yield self._coro_to_def(self.rtm.init_task(task_id))
        self.rtm.start_task(task_id)
        computing_node = ComputingNode.create(
            node_id='abc',
            name='abc',
        )
        # when
        res = yield self._coro_to_def(
            self.rtm.get_next_subtask(task_id, computing_node)
        )
        row = RequestedSubtask.get(
            RequestedSubtask.subtask_id == res.subtask_id)
        # then
        self.assertEqual(row.task_id, task_id)
        self.assertEqual(row.computing_node, computing_node)
        mock_client.next_subtask.assert_called_once_with(task_id)

    @inlineCallbacks
    def test_verify(self):
        # given
        mock_client = self._mock_client_create()
        self._add_next_subtask_to_client_mock(mock_client)
        mock_client.verify.return_value = True

        task_id = self._create_task()
        yield self._coro_to_def(self.rtm.init_task(task_id))
        self.rtm.start_task(task_id)
        computing_node = ComputingNode.create(
            node_id='abc',
            name='abc',
        )
        subtask = yield self._coro_to_def(
            self.rtm.get_next_subtask(task_id, computing_node)
        )
        # The second call should return false so the client will shut down
        mock_client.has_pending_subtasks.return_value = False
        subtask_id = subtask.subtask_id
        # when
        res = yield self._coro_to_def(
            self.rtm.verify(task_id, subtask.subtask_id)
        )
        task_row = RequestedTask.get(RequestedTask.task_id == task_id)
        subtask_row = RequestedSubtask.get(
            RequestedSubtask.subtask_id == subtask_id)
        # then
        self.assertTrue(res)
        mock_client.verify.assert_called_once_with(task_id, subtask.subtask_id)
        mock_client.shutdown.assert_called_once_with()
        self.assertTrue(task_row.status.is_completed())
        self.assertTrue(subtask_row.status.is_finished())

    @inlineCallbacks
    def test_verify_failed(self):
        # given
        mock_client = self._mock_client_create()
        self._add_next_subtask_to_client_mock(mock_client)
        mock_client.verify.return_value = False

        task_id = self._create_task()
        yield self._coro_to_def(self.rtm.init_task(task_id))
        self.rtm.start_task(task_id)
        computing_node = ComputingNodeDefinition(
            node_id='abc',
            name='abc',
        )
        subtask = yield self._coro_to_def(
            self.rtm.get_next_subtask(task_id, computing_node)
        )
        subtask_id = subtask.subtask_id
        # when
        res = yield self._coro_to_def(
            self.rtm.verify(task_id, subtask.subtask_id)
        )
        task_row = RequestedTask.get(RequestedTask.task_id == task_id)
        subtask_row = RequestedSubtask.get(
            RequestedSubtask.subtask_id == subtask_id)
        # then
        self.assertFalse(res)
        mock_client.verify.assert_called_once_with(task_id, subtask.subtask_id)
        mock_client.shutdown.assert_not_called()
        self.assertTrue(task_row.status.is_active())
        self.assertEqual(subtask_row.status, SubtaskStatus.failure)

    @inlineCallbacks
    def test_abort(self):
        # given
        mock_client = self._mock_client_create()
        self._add_next_subtask_to_client_mock(mock_client)

        task_id = self._create_task()
        yield self._coro_to_def(self.rtm.init_task(task_id))
        self.rtm.start_task(task_id)
        computing_node = ComputingNodeDefinition(
            node_id='abc',
            name='abc',
        )
        subtask = yield self._coro_to_def(
            self.rtm.get_next_subtask(task_id, computing_node)
        )
        subtask_id = subtask.subtask_id
        # when
        yield self._coro_to_def(self.rtm.abort_task(task_id))
        task_row = RequestedTask.get(RequestedTask.task_id == task_id)
        subtask_row = RequestedSubtask.get(
            RequestedSubtask.subtask_id == subtask_id)
        # then
        mock_client.shutdown.assert_called_once_with()
        self.assertEqual(task_row.status, TaskStatus.aborted)
        self.assertEqual(subtask_row.status, SubtaskStatus.cancelled)

    def _build_golem_params(self) -> CreateTaskParams:
        return CreateTaskParams(
            app_id='a',
            name='a',
            environment='a',
            task_timeout=1,
            subtask_timeout=1,
            output_directory=self.new_path / 'output',
            resources=[],
            max_subtasks=1,
            max_price_per_hour=1,
            concent_enabled=False,
        )

    def _create_task(self):
        golem_params = self._build_golem_params()
        app_params = {}
        task_id = self.rtm.create_task(golem_params, app_params)
        return task_id

    def _mock_client_create(self):
        mock_client = AsyncMock(spec=RequestorAppClient)
        create_f = asyncio.Future()
        create_f.set_result(mock_client)
        self._patch_async(
            'golem.task.requestedtaskmanager.RequestorAppClient.create',
            return_value=create_f)

        return mock_client

    @staticmethod
    def _add_next_subtask_to_client_mock(mock_client):
        result = Subtask(subtask_id='', params={}, resources=[])
        mock_client.next_subtask.return_value = result
        mock_client.has_pending_subtasks.return_value = True

    def _patch_async(self, name, *args, **kwargs):
        patcher = patch(name, *args, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    @staticmethod
    def _coro_to_def(coroutine):
        task = asyncio.ensure_future(coroutine)
        return deferred_from_future(task)
