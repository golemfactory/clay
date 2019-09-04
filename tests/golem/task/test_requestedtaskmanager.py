import asyncio

from freezegun import freeze_time
from golem_task_api.client import RequestorAppClient
from golem_task_api.structs import Subtask
from mock import Mock, patch, MagicMock
import pytest

from golem.app_manager import AppManager
from golem.model import default_now, RequestedTask, RequestedSubtask
from golem.task.envmanager import EnvironmentManager
from golem.task.requestedtaskmanager import (
    ComputingNode,
    CreateTaskParams,
    RequestedTaskManager,
    ComputingNodeDefinition,
)
from golem.task.taskstate import TaskStatus, SubtaskStatus
from golem.testutils import AsyncDatabaseFixture


class AsyncMock(MagicMock):
    async def __call__(self, *args, **kwargs):
        return super().__call__(*args, **kwargs)


class TestRequestedTaskManager(AsyncDatabaseFixture):

    def setup_method(self, method):
        super().setup_method(method)
        self.env_manager = Mock(spec=EnvironmentManager)
        self.app_manager = Mock(spec=AppManager)
        self.public_key = str.encode('0xdeadbeef')
        self.rtm = RequestedTaskManager(
            env_manager=self.env_manager,
            app_manager=self.app_manager,
            public_key=self.public_key,
            root_path=self.new_path
        )

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

    @pytest.mark.asyncio
    async def test_init_task(self, monkeypatch):
        # given
        mock_client = self._mock_client_create(monkeypatch)

        task_id = self._create_task()
        # when
        await self.rtm.init_task(task_id)
        row = RequestedTask.get(RequestedTask.task_id == task_id)
        # then
        assert row.status == TaskStatus.creating
        mock_client.create_task.assert_called_once_with(
            row.task_id,
            row.max_subtasks,
            row.app_params
        )
        self.app_manager.enabled.assert_called_once_with(row.app_id)

    @pytest.mark.asyncio
    async def test_init_task_wrong_status(self, monkeypatch):
        # given
        self._mock_client_create(monkeypatch)

        task_id = self._create_task()
        # when
        await self.rtm.init_task(task_id)
        # Start task to change the status
        self.rtm.start_task(task_id)
        # then
        with pytest.raises(RuntimeError):
            await self.rtm.init_task(task_id)

    @pytest.mark.asyncio
    async def test_start_task(self, monkeypatch):
        # given
        self._mock_client_create(monkeypatch)

        task_id = self._create_task()
        await self.rtm.init_task(task_id)
        # when
        self.rtm.start_task(task_id)
        # then
        row = RequestedTask.get(RequestedTask.task_id == task_id)
        assert row.status == TaskStatus.waiting

    def test_task_exists(self):
        task_id = self._create_task()
        assert self.rtm.task_exists(task_id) is True

    def test_task_not_exists(self):
        task_id = 'a'
        assert self.rtm.task_exists(task_id) is False

    @pytest.mark.asyncio
    async def test_has_pending_subtasks(self, monkeypatch):
        # given
        mock_client = self._mock_client_create(monkeypatch)
        mock_client.has_pending_subtasks.return_value = True

        task_id = self._create_task()
        await self.rtm.init_task(task_id)
        self.rtm.start_task(task_id)
        # when
        res = await self.rtm.has_pending_subtasks(task_id)
        # then
        assert res is True
        mock_client.has_pending_subtasks.assert_called_once_with(task_id)

    @pytest.mark.asyncio
    async def test_get_next_subtask(self, monkeypatch):
        # given
        mock_client = self._mock_client_create(monkeypatch)
        self._add_next_subtask_to_client_mock(mock_client)

        task_id = self._create_task()
        await self.rtm.init_task(task_id)
        self.rtm.start_task(task_id)
        computing_node = ComputingNode.create(
            node_id='abc',
            name='abc',
        )
        # when
        res = await self.rtm.get_next_subtask(task_id, computing_node)

        row = RequestedSubtask.get(
            RequestedSubtask.subtask_id == res.subtask_id)
        # then
        assert row.task_id == task_id
        assert row.computing_node == computing_node
        mock_client.next_subtask.assert_called_once_with(task_id)

    @pytest.mark.asyncio
    async def test_verify(self, monkeypatch):
        # given
        mock_client = self._mock_client_create(monkeypatch)
        self._add_next_subtask_to_client_mock(mock_client)
        mock_client.verify.return_value = True

        task_id = self._create_task()
        await self.rtm.init_task(task_id)
        self.rtm.start_task(task_id)
        computing_node = ComputingNode.create(
            node_id='abc',
            name='abc',
        )
        subtask = await self.rtm.get_next_subtask(task_id, computing_node)

        # The second call should return false so the client will shut down
        mock_client.has_pending_subtasks.return_value = False
        subtask_id = subtask.subtask_id
        # when
        res = await self.rtm.verify(task_id, subtask.subtask_id)

        task_row = RequestedTask.get(RequestedTask.task_id == task_id)
        subtask_row = RequestedSubtask.get(
            RequestedSubtask.subtask_id == subtask_id)
        # then
        assert res is True
        mock_client.verify.assert_called_once_with(task_id, subtask.subtask_id)
        mock_client.shutdown.assert_called_once_with()
        assert task_row.status.is_completed() is True
        assert subtask_row.status.is_finished() is True

    @pytest.mark.asyncio
    async def test_verify_failed(self, monkeypatch):
        # given
        mock_client = self._mock_client_create(monkeypatch)
        self._add_next_subtask_to_client_mock(mock_client)
        mock_client.verify.return_value = False

        task_id = self._create_task()
        await self.rtm.init_task(task_id)
        self.rtm.start_task(task_id)
        computing_node = ComputingNodeDefinition(
            node_id='abc',
            name='abc',
        )
        subtask = await self.rtm.get_next_subtask(task_id, computing_node)

        subtask_id = subtask.subtask_id
        # when
        res = await self.rtm.verify(task_id, subtask.subtask_id)

        task_row = RequestedTask.get(RequestedTask.task_id == task_id)
        subtask_row = RequestedSubtask.get(
            RequestedSubtask.subtask_id == subtask_id)
        # then
        assert res is False
        mock_client.verify.assert_called_once_with(task_id, subtask.subtask_id)
        mock_client.shutdown.assert_not_called()
        assert task_row.status.is_active() is True
        assert subtask_row.status == SubtaskStatus.failure

    @pytest.mark.asyncio
    async def test_abort(self, monkeypatch):
        # given
        mock_client = self._mock_client_create(monkeypatch)
        self._add_next_subtask_to_client_mock(mock_client)

        task_id = self._create_task()
        await self.rtm.init_task(task_id)
        self.rtm.start_task(task_id)
        computing_node = ComputingNodeDefinition(
            node_id='abc',
            name='abc',
        )
        subtask = await self.rtm.get_next_subtask(task_id, computing_node)

        subtask_id = subtask.subtask_id
        # when
        await self.rtm.abort_task(task_id)
        task_row = RequestedTask.get(RequestedTask.task_id == task_id)
        subtask_row = RequestedSubtask.get(
            RequestedSubtask.subtask_id == subtask_id)
        # then
        mock_client.shutdown.assert_called_once_with()
        assert task_row.status == TaskStatus.aborted
        assert subtask_row.status == SubtaskStatus.cancelled

    def _build_golem_params(self) -> CreateTaskParams:
        return CreateTaskParams(
            app_id='a',
            name='a',
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

    @staticmethod
    def _mock_client_create(monkeypatch):
        mock_client = AsyncMock(spec=RequestorAppClient)

        @asyncio.coroutine
        def mock_create(*_args, **_kwargs):
            return mock_client

        monkeypatch.setattr(
            RequestorAppClient,
            'create',
            mock_create)

        return mock_client

    @staticmethod
    def _add_next_subtask_to_client_mock(mock_client):
        result = Subtask(subtask_id='', params={}, resources=[])
        mock_client.next_subtask.return_value = result
        mock_client.has_pending_subtasks.return_value = True
