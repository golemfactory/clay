import asyncio

from dataclasses import asdict
from golem_task_api.client import RequestorAppClient
from golem_task_api.structs import Subtask
from mock import Mock, patch
import pytest
from twisted.internet.defer import inlineCallbacks
from twisted.trial.unittest import TestCase as TwistedTestCase

from golem.core.common import install_reactor
from golem.tools.testwithreactor import uninstall_reactor
from golem.core.deferred import deferred_from_future
from golem.model import default_now, RequestedTask, RequestedSubtask
from golem.task.envmanager import EnvironmentManager
from golem.task.requestedtaskmanager import (
    ComputingNode,
    CreateTaskParams,
    RequestedTaskManager,
)
from golem.task.taskstate import TaskStatus, SubtaskStatus
from golem.testutils import DatabaseFixture


class TestRequestedTaskManager(DatabaseFixture, TwistedTestCase):
    @classmethod
    def setUpClass(cls):
        try:
            uninstall_reactor()  # Because other tests don't clean up
        except AttributeError:
            pass
        install_reactor()

    @classmethod
    def tearDownClass(cls):
        uninstall_reactor()

    def setUp(self):
        super().setUp()
        self.env_manager = Mock(spec=EnvironmentManager)
        self.public_key = str.encode('0xdeadbeef')
        self.rtm = RequestedTaskManager(
            env_manager=self.env_manager,
            public_key=self.public_key,
            root_path=self.new_path
        )

    def tearDown(self):
        super().tearDown()

    def test_create_task(self):
        # given
        golem_params = self._build_golem_params()
        app_params = {}
        # when
        task_id = self.rtm.create_task(golem_params, app_params)
        # then
        row = RequestedTask.get(RequestedTask.task_id == task_id)
        assert row.status == TaskStatus.creating
        assert row.start_time < default_now()

    @inlineCallbacks
    def test_init_task(self):
        # given
        mock_client = self._mock_client_create()
        self._add_create_task_to_client_mock(mock_client)

        task_id, golem_params, _ = self._create_task()
        # when
        yield self._coro_to_def(self.rtm.init_task(task_id))
        row = RequestedTask.get(RequestedTask.task_id == task_id)
        # then
        assert row.status == TaskStatus.creating
        assert mock_client.create_task.called_once_with(
            task_id,
            golem_params.max_subtasks,
            asdict(golem_params)
        )
        self.env_manager.enabled.assert_called_once_with(row.environment)

    @inlineCallbacks
    def test_init_task_wrong_status(self):
        # given
        mock_client = self._mock_client_create()
        self._add_create_task_to_client_mock(mock_client)

        task_id, _, _ = self._create_task()
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
        mock_client = self._mock_client_create()
        self._add_create_task_to_client_mock(mock_client)

        task_id, _, _ = self._create_task()
        yield self._coro_to_def(self.rtm.init_task(task_id))
        # when
        self.rtm.start_task(task_id)
        # then
        row = RequestedTask.get(RequestedTask.task_id == task_id)
        assert row.status == TaskStatus.waiting

    def test_task_exists(self):
        task_id, _, _ = self._create_task()
        self.assertTrue(self.rtm.task_exists(task_id))

    def test_task_not_exists(self):
        task_id = 'a'
        self.assertFalse(self.rtm.task_exists(task_id))

    @inlineCallbacks
    def test_has_pending_subtasks(self):
        # given
        mock_client = self._mock_client_create()
        self._add_create_task_to_client_mock(mock_client)
        self._add_has_pending_subtasks_to_client_mock(mock_client)

        task_id, _, _ = self._create_task()
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
        self._add_create_task_to_client_mock(mock_client)
        self._add_next_subtask_to_client_mock(mock_client)

        task_id, _, _ = self._create_task()
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
        # then
        self.assertEqual(res.task_id, task_id)
        self.assertEqual(res.computing_node, computing_node)
        mock_client.next_subtask.assert_called_once_with(task_id)

    @inlineCallbacks
    def test_verify(self):
        # given
        mock_client = self._mock_client_create()
        self._add_create_task_to_client_mock(mock_client)
        self._add_next_subtask_to_client_mock(mock_client)
        self._add_verify_to_client_mock(mock_client)

        task_id, _, _ = self._create_task()
        yield self._coro_to_def(self.rtm.init_task(task_id))
        self.rtm.start_task(task_id)
        computing_node = ComputingNode.create(
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
        self.assertTrue(res)
        mock_client.verify.assert_called_once_with(task_id, subtask.subtask_id)
        self.assertTrue(task_row.status.is_completed())
        self.assertTrue(subtask_row.status.is_finished())

    @inlineCallbacks
    def test_verify_failed(self):
        # given
        mock_client = self._mock_client_create()
        self._add_create_task_to_client_mock(mock_client)
        self._add_next_subtask_to_client_mock(mock_client)
        self._add_verify_to_client_mock(mock_client, False)

        task_id, _, _ = self._create_task()
        yield self._coro_to_def(self.rtm.init_task(task_id))
        self.rtm.start_task(task_id)
        computing_node = ComputingNode.create(
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
        self.assertTrue(task_row.status.is_active())
        self.assertEqual(subtask_row.status, SubtaskStatus.failure)

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
        return task_id, golem_params, app_params

    def _mock_client_create(self):
        mock_client = Mock(spec=RequestorAppClient)
        f = asyncio.Future()
        f.set_result(mock_client)
        self._patch_async(
            'golem.task.requestedtaskmanager.RequestorAppClient.create',
            return_value=f)
        return mock_client

    @staticmethod
    def _add_create_task_to_client_mock(mock_client):
        f = asyncio.Future()
        f.set_result(None)
        mock_client.create_task = Mock(return_value=f)

    @staticmethod
    def _add_has_pending_subtasks_to_client_mock(mock_client, result=True):
        f = asyncio.Future()
        f.set_result(result)
        mock_client.has_pending_subtasks = Mock(return_value=f)

    @staticmethod
    def _add_next_subtask_to_client_mock(mock_client):
        result = Mock(spec=Subtask)
        f = asyncio.Future()
        f.set_result(result)
        mock_client.next_subtask = Mock(return_value=f)
        return result

    @staticmethod
    def _add_verify_to_client_mock(mock_client, result=True):
        f = asyncio.Future()
        f.set_result(result)
        mock_client.verify = Mock(return_value=f)

    def _patch_async(self, name, *args, **kwargs):
        patcher = patch(name, *args, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    @staticmethod
    def _coro_to_def(coroutine):
        task = asyncio.ensure_future(coroutine)
        return deferred_from_future(task)
