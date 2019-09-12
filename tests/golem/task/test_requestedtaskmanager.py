# pylint: disable=redefined-outer-name
# ^^ Pytest fixtures in the same file require the same name

import asyncio
import json
from pathlib import Path

from freezegun import freeze_time
from golem_task_api.client import RequestorAppClient
from golem_task_api.structs import Subtask
from mock import Mock
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
from golem.testutils import pytest_database_fixture  # noqa pylint: disable=unused-import
from tests.utils.asyncio import AsyncMock


@pytest.fixture
def mock_client(monkeypatch):
    client_mock = AsyncMock(spec=RequestorAppClient)

    @asyncio.coroutine
    def mock_create(*_args, **_kwargs):
        return client_mock

    monkeypatch.setattr(RequestorAppClient, 'create', mock_create)

    client_mock.create_task.return_value = Mock(
        env_id='env_id',
        prerequisites_json='null'
    )
    return client_mock


@pytest.mark.usefixtures('pytest_database_fixture')
class TestRequestedTaskManager():

    @pytest.fixture(autouse=True)
    def setup_method(self, tmpdir):
        # TODO: Replace with tmp_path when pytest is updated to 5.x
        self.tmp_path = Path(tmpdir)

        self.env_manager = Mock(spec=EnvironmentManager)
        self.app_manager = Mock(spec=AppManager)
        self.public_key = str.encode('0xdeadbeef')
        self.rtm_path = self.tmp_path / 'rtm'
        self.rtm_path.mkdir()
        self.rtm = RequestedTaskManager(
            env_manager=self.env_manager,
            app_manager=self.app_manager,
            public_key=self.public_key,
            root_path=self.rtm_path
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
            assert (self.rtm_path / golem_params.app_id / task_id).exists()

    @pytest.mark.asyncio
    async def test_init_task(self, mock_client):
        # given
        task_id = self._create_task()
        env_id = 'test_env'
        prerequisites = {'key': 'value'}
        mock_client.create_task.return_value = Mock(
            env_id=env_id,
            prerequisites_json=json.dumps(prerequisites)
        )
        # when
        await self.rtm.init_task(task_id)
        row = RequestedTask.get(RequestedTask.task_id == task_id)
        # then
        assert row.status == TaskStatus.creating
        assert row.env_id == env_id
        assert row.prerequisites == prerequisites
        mock_client.create_task.assert_called_once_with(
            row.task_id,
            row.max_subtasks,
            row.app_params
        )
        self.app_manager.enabled.assert_called_once_with(row.app_id)

    @pytest.mark.asyncio
    async def test_init_task_wrong_status(self, mock_client):
        # given
        task_id = self._create_task()
        # when
        await self.rtm.init_task(task_id)
        # Start task to change the status
        self.rtm.start_task(task_id)
        # then
        with pytest.raises(RuntimeError):
            await self.rtm.init_task(task_id)

    @pytest.mark.asyncio
    async def test_start_task(self, mock_client):
        # given
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
    async def test_has_pending_subtasks(self, mock_client):
        # given
        mock_client.has_pending_subtasks.return_value = True
        task_id = await self._start_task()

        # when
        res = await self.rtm.has_pending_subtasks(task_id)
        # then
        assert res is True
        mock_client.has_pending_subtasks.assert_called_once_with(task_id)

    @pytest.mark.asyncio
    async def test_get_next_subtask(self, mock_client):
        # given
        self._add_next_subtask_to_client_mock(mock_client)
        task_id = await self._start_task()

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
    async def test_verify(self, mock_client):
        # given
        self._add_next_subtask_to_client_mock(mock_client)
        mock_client.verify.return_value = True
        task_id = await self._start_task()

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
    async def test_verify_failed(self, mock_client):
        # given
        self._add_next_subtask_to_client_mock(mock_client)
        mock_client.verify.return_value = False

        task_id = await self._start_task()
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
    async def test_abort(self, mock_client):
        # given
        self._add_next_subtask_to_client_mock(mock_client)

        task_id = await self._start_task()
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

    @pytest.mark.asyncio
    async def test_task_timeout(self, mock_client):
        task_timeout = 0.1
        task_id = self._create_task(task_timeout=task_timeout)
        await self.rtm.init_task(task_id)
        self.rtm.start_task(task_id)
        assert not self.rtm.is_task_finished(task_id)

        # Unfortunately feezegun doesn't mock asyncio's time
        # and can't be used here
        await asyncio.sleep(task_timeout)
        assert self.rtm.is_task_finished(task_id)

    @pytest.mark.asyncio
    async def test_restart_task(self, mock_client):
        task_timeout = 0.1
        task_id = await self._start_task(task_timeout=task_timeout)
        # Wait for the task to timeout
        await asyncio.sleep(task_timeout)
        assert self.rtm.is_task_finished(task_id)

        await self.rtm.restart_task(task_id)
        assert not self.rtm.is_task_finished(task_id)

    async def _start_task(self, **golem_params):
        task_id = self._create_task(**golem_params)
        await self.rtm.init_task(task_id)
        self.rtm.start_task(task_id)
        return task_id

    def _build_golem_params(self, task_timeout=1) -> CreateTaskParams:
        return CreateTaskParams(
            app_id='a',
            name='a',
            task_timeout=task_timeout,
            subtask_timeout=1,
            output_directory=self.tmp_path / 'output',
            resources=[],
            max_subtasks=1,
            max_price_per_hour=1,
            concent_enabled=False,
        )

    def _create_task(self, **golem_params):
        golem_params = self._build_golem_params(**golem_params)
        app_params = {}
        task_id = self.rtm.create_task(golem_params, app_params)
        return task_id

    @staticmethod
    def _add_next_subtask_to_client_mock(client_mock):
        result = Subtask(subtask_id='', params={}, resources=[])
        client_mock.next_subtask.return_value = result
        client_mock.has_pending_subtasks.return_value = True
