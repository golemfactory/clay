# pylint: disable=redefined-outer-name,no-member
# ^^ Pytest fixtures in the same file require the same name

import asyncio
from pathlib import Path

from freezegun import freeze_time
from golem_task_api.client import RequestorAppClient
from golem_task_api.enums import VerifyResult
from golem_task_api.structs import Subtask, Infrastructure
from mock import ANY, call, MagicMock, Mock
import pytest
from twisted.internet import defer

from golem.apps.manager import AppManager
from golem.core.common import default_now
from golem.model import RequestedTask, RequestedSubtask
from golem.task.envmanager import EnvironmentManager
from golem.task import requestedtaskmanager
from golem.task.requestedtaskmanager import (
    CreateTaskParams,
    RequestedTaskManager,
    ComputingNodeDefinition)
from golem.task.taskstate import TaskStatus, SubtaskStatus, TaskState
from golem.testutils import pytest_database_fixture  # noqa pylint: disable=unused-import
from tests.factories.task import requestedtaskmanager as rtm_factory
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
        prerequisites={},
        inf_requirements=Infrastructure(min_memory_mib=2000.),
    )
    return client_mock


@pytest.mark.usefixtures('pytest_database_fixture')
class TestRequestedTaskManager:

    @pytest.fixture(autouse=True)
    def setup_method(self, tmpdir, monkeypatch):
        self.frozen_time = None
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

        self.env_manager.environment().install_prerequisites.return_value = \
            defer.succeed(True)

        monkeypatch.setattr(
            requestedtaskmanager,
            '_build_legacy_task_state',
            lambda *_: TaskState())

    @pytest.mark.asyncio
    @pytest.mark.freeze_time("1000")
    async def test_restore_tasks_timedout(self, freezer, mock_client):
        # given
        self._add_next_subtask_to_client_mock(mock_client)
        self.rtm._time_out_task = Mock()
        self.rtm._time_out_subtask = Mock()

        task_id = await self._create_task()
        await self.rtm.init_task(task_id)
        self.rtm.start_task(task_id)
        computing_node = self._get_computing_node()
        subtask = await self.rtm.get_next_subtask(task_id, computing_node)
        freezer.move_to("1010")
        # when
        self.rtm.restore_tasks()
        # then
        self.rtm._time_out_task.assert_called_once_with(task_id)
        self.rtm._time_out_subtask.assert_called_once_with(
            task_id,
            subtask.subtask_id
        )

    @pytest.mark.asyncio
    async def test_restore_tasks_schedule(self, mock_client, monkeypatch):
        # given
        self._add_next_subtask_to_client_mock(mock_client)

        task_id = await self._create_task(
            task_timeout=20,
            subtask_timeout=20)
        await self.rtm.init_task(task_id)
        self.rtm.start_task(task_id)
        computing_node = self._get_computing_node()
        subtask = await self.rtm.get_next_subtask(task_id, computing_node)
        # when
        schedule = MagicMock()
        monkeypatch.setattr(self.rtm._timeouts, 'schedule', schedule)
        self.rtm.restore_tasks()
        # then
        assert schedule.call_count == 2
        schedule.assert_has_calls([
            call(subtask.subtask_id, ANY, ANY),
            call(task_id, ANY, ANY),
        ])

    @pytest.mark.asyncio
    async def test_create_task(self):
        # given
        golem_params = self._build_golem_params()
        app_params = {}
        # when
        task_id = await self.rtm.create_task(golem_params, app_params)
        # then
        row = RequestedTask.get(RequestedTask.task_id == task_id)
        assert row.status == TaskStatus.creating
        assert row.start_time is None
        assert (self.rtm_path / golem_params.app_id / task_id).exists()

    @pytest.mark.asyncio
    async def test_init_task(self, mock_client):
        # given
        task_id = await self._create_task()
        env_id = 'test_env'
        prerequisites = {'key': 'value'}
        mock_client.create_task.return_value = Mock(
            env_id=env_id,
            prerequisites=prerequisites,
            inf_requirements=Infrastructure(min_memory_mib=2000.),
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
        assert self.rtm.has_unfinished_tasks()

    @pytest.mark.asyncio
    async def test_init_task_wrong_status(self, mock_client):
        # given
        task_id = await self._create_task()
        # when
        await self.rtm.init_task(task_id)
        # Start task to change the status
        self.rtm.start_task(task_id)
        # then
        with pytest.raises(RuntimeError):
            await self.rtm.init_task(task_id)

    @pytest.mark.asyncio
    async def test_start_task(self, mock_client):
        with freeze_time() as freezer:
            # given
            task_id = await self._create_task()
            await self.rtm.init_task(task_id)
            # when
            self.rtm.start_task(task_id)
            freezer.tick()
            # then
            row = RequestedTask.get(RequestedTask.task_id == task_id)
            assert row.status == TaskStatus.waiting
            assert row.start_time < default_now()

    @pytest.mark.asyncio
    async def test_error_creating(self, mock_client):
        # given
        task_id = await self._create_task()
        # when
        await self.rtm.init_task(task_id)
        self.rtm.error_creating(task_id)
        # then
        row = RequestedTask.get(RequestedTask.task_id == task_id)
        assert row.status == TaskStatus.errorCreating

    @pytest.mark.asyncio
    async def test_error_creating_wrong_status(self, mock_client):
        # given
        task_id = await self._create_task()
        # when
        await self.rtm.init_task(task_id)
        # Start task to change the status
        self.rtm.start_task(task_id)
        # then
        with pytest.raises(RuntimeError):
            self.rtm.error_creating(task_id)

    @pytest.mark.asyncio
    async def test_task_exists(self):
        task_id = await self._create_task()
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
        computing_node = self._get_computing_node()

        # when
        res = await self.rtm.get_next_subtask(task_id, computing_node)

        row = RequestedSubtask.get(
            RequestedSubtask.task == task_id,
            RequestedSubtask.subtask_id == res.subtask_id)
        # then
        assert row.task_id == task_id
        assert row.computing_node.node_id == computing_node.node_id
        assert row.computing_node.name == computing_node.name
        mock_client.next_subtask.assert_called_once_with(
            task_id=task_id,
            subtask_id=res.subtask_id,
            opaque_node_id=ANY
        )

    @pytest.mark.asyncio
    @pytest.mark.freeze_time("1000")
    async def test_verify(self, freezer, mock_client):
        # given
        self._add_next_subtask_to_client_mock(mock_client)
        mock_client.verify.return_value = (VerifyResult.SUCCESS, '')
        task_id = await self._start_task()

        subtask = await self.rtm.get_next_subtask(
            task_id,
            self._get_computing_node(),
        )

        # The second call should return false so the client will shut down
        mock_client.has_pending_subtasks.return_value = False
        subtask_id = subtask.subtask_id
        # when
        freezer.move_to("1010")
        res = await self.rtm._verify(task_id, subtask.subtask_id)

        task_row = RequestedTask.get(RequestedTask.task_id == task_id)
        subtask_row = RequestedSubtask.get(
            RequestedSubtask.task == task_id,
            RequestedSubtask.subtask_id == subtask_id)
        # then
        assert res is VerifyResult.SUCCESS
        mock_client.verify.assert_called_once_with(task_id, subtask.subtask_id)
        mock_client.shutdown.assert_called_once_with()
        assert task_row.status.is_completed() is True
        assert subtask_row.status.is_finished() is True
        assert not self.rtm.has_unfinished_tasks()

    @pytest.mark.asyncio
    @pytest.mark.freeze_time("1000")
    async def test_verify_failed(self, freezer, mock_client):
        # given
        self._add_next_subtask_to_client_mock(mock_client)
        mock_client.verify.return_value = False

        task_id = await self._start_task()
        subtask = await self.rtm.get_next_subtask(
            task_id, self._get_computing_node(),
        )

        subtask_id = subtask.subtask_id
        # when
        freezer.move_to("1010")
        res = await self.rtm._verify(task_id, subtask.subtask_id)

        task_row = RequestedTask.get(RequestedTask.task_id == task_id)
        subtask_row = RequestedSubtask.get(
            RequestedSubtask.task == task_id,
            RequestedSubtask.subtask_id == subtask_id)
        # then
        assert res is VerifyResult.FAILURE
        mock_client.verify.assert_called_once_with(task_id, subtask.subtask_id)
        mock_client.shutdown.assert_not_called()
        assert task_row.status.is_active() is True
        assert subtask_row.status == SubtaskStatus.failure
        assert self.rtm.has_unfinished_tasks()

    @pytest.mark.asyncio
    @pytest.mark.freeze_time("1000")
    async def test_abort(self, freezer, mock_client):
        # given
        self._add_next_subtask_to_client_mock(mock_client)

        task_id = await self._start_task()
        subtask = await self.rtm.get_next_subtask(
            task_id,
            self._get_computing_node(),
        )

        subtask_id = subtask.subtask_id
        # when
        freezer.move_to("1010")
        await self.rtm.abort_task(task_id)
        task_row = RequestedTask.get(RequestedTask.task_id == task_id)
        subtask_row = RequestedSubtask.get(
            RequestedSubtask.task == task_id,
            RequestedSubtask.subtask_id == subtask_id)
        # then
        mock_client.abort_task.assert_called_once_with(task_id)
        mock_client.shutdown.assert_called_once_with()
        assert task_row.status == TaskStatus.aborted
        assert subtask_row.status == SubtaskStatus.cancelled
        assert not self.rtm.has_unfinished_tasks()

    @pytest.mark.asyncio
    async def test_task_timeout(self, mock_client):
        task_timeout = 0.1
        task_id = await self._create_task(task_timeout=task_timeout)
        await self.rtm.init_task(task_id)
        self.rtm.start_task(task_id)
        assert not self.rtm.is_task_finished(task_id)

        # Unfortunately feezegun doesn't mock asyncio's time
        # and can't be used here
        await asyncio.sleep(task_timeout)

        assert self.rtm.is_task_finished(task_id)
        mock_client.abort_task.assert_called_once_with(task_id)
        mock_client.shutdown.assert_called_once_with()
        assert not self.rtm.has_unfinished_tasks()

    @pytest.mark.asyncio
    async def test_task_timeout_with_subtask(self, mock_client):
        self._add_next_subtask_to_client_mock(mock_client)
        task_timeout = 1
        task_id = await self._start_task(task_timeout=task_timeout)
        subtask_id = (await self.rtm.get_next_subtask(
            task_id, self._get_computing_node()
        )).subtask_id

        # Unfortunately feezegun doesn't mock asyncio's time
        # and can't be used here
        await asyncio.sleep(task_timeout)

        task = RequestedTask.get(RequestedTask.task_id == task_id)
        subtask = RequestedSubtask.get(
            RequestedSubtask.task == task_id,
            RequestedSubtask.subtask_id == subtask_id)
        assert task.status == TaskStatus.timeout
        assert subtask.status == SubtaskStatus.timeout
        assert not self.rtm.has_unfinished_tasks()

    @pytest.mark.asyncio
    async def test_subtask_timeout(self, mock_client):
        self._add_next_subtask_to_client_mock(mock_client)
        task_timeout = 10
        subtask_timeout = 1
        task_id = await self._start_task(
            task_timeout=task_timeout,
            subtask_timeout=subtask_timeout)
        subtask_id = (await self.rtm.get_next_subtask(
            task_id, self._get_computing_node()
        )).subtask_id

        # Unfortunately feezegun doesn't mock asyncio's time
        # and can't be used here
        await asyncio.sleep(subtask_timeout)

        subtask = RequestedSubtask.get(
            RequestedSubtask.task == task_id,
            RequestedSubtask.subtask_id == subtask_id)
        assert subtask.status == SubtaskStatus.timeout
        mock_client.abort_subtask.assert_called_once_with(task_id, subtask_id)

    @pytest.mark.asyncio
    async def test_get_started_tasks(self, mock_client):
        # given
        task_id = await self._create_task()
        await self.rtm.init_task(task_id)
        # when
        results = self.rtm.get_started_tasks()
        assert not results
        self.rtm.start_task(task_id)
        results = self.rtm.get_started_tasks()
        # then
        assert results
        assert len(results) == 1
        assert list(results)[0].task_id == task_id

    # pylint: disable=unused-argument
    @pytest.mark.asyncio
    async def test_restart_task(self, mock_client, monkeypatch):
        task_id = await self._start_task(task_timeout=0.1)

        app_client = rtm_factory.MockRequestorAppClient()
        get_app_client = AsyncMock(return_value=app_client)
        monkeypatch.setattr(self.rtm, '_get_app_client', get_app_client)

        await self.rtm.restart_task(task_id)
        assert app_client.create_task.called
        assert app_client.abort_task.called

    @pytest.mark.asyncio
    async def test_restart_task_after_timeout(self, mock_client, monkeypatch):
        task_timeout = 1
        task_id = await self._start_task(task_timeout=task_timeout)

        # Wait for the task to timeout
        await asyncio.sleep(task_timeout)
        assert self.rtm.is_task_finished(task_id)

        app_client = rtm_factory.MockRequestorAppClient()
        get_app_client = AsyncMock(return_value=app_client)
        monkeypatch.setattr(self.rtm, '_get_app_client', get_app_client)

        await self.rtm.restart_task(task_id)
        assert app_client.create_task.called
        assert not app_client.abort_task.called

    @pytest.mark.asyncio
    async def test_delete_task(self, mock_client):
        task_id = await self._start_task(task_timeout=10.)
        assert self.rtm.get_requested_task(task_id)

        await self.rtm.delete_task(task_id)
        assert not self.rtm.get_requested_task(task_id)

    # pylint: enable=unused-argument

    @pytest.mark.asyncio
    async def test_duplicate_task(self, mock_client):
        resources_dir = self.tmp_path / 'resources'
        resources_dir.mkdir()
        resource = resources_dir / 'file'
        resource.touch()
        task_id = await self._start_task(resources=[resource])
        new_output_dir = self.tmp_path / 'dup_output'

        duplicated_task_id = \
            await self.rtm.duplicate_task(task_id, new_output_dir)

        assert duplicated_task_id != task_id
        task = RequestedTask.get(RequestedTask.task_id == task_id)
        duplicated_task = RequestedTask.get(
            RequestedTask.task_id == duplicated_task_id)
        assert task.app_params == duplicated_task.app_params
        assert task.task_timeout == duplicated_task.task_timeout
        assert task.subtask_timeout == duplicated_task.subtask_timeout
        assert task.max_subtasks == duplicated_task.max_subtasks
        assert task.max_price_per_hour == duplicated_task.max_price_per_hour
        assert task.concent_enabled == duplicated_task.concent_enabled
        assert Path(duplicated_task.output_directory) == new_output_dir

    @pytest.mark.asyncio
    async def test_discard_subtasks(self, mock_client):
        self._add_next_subtask_to_client_mock(mock_client)
        task_id = await self._start_task()
        subtask = await self.rtm.get_next_subtask(
            task_id,
            self._get_computing_node(),
        )
        self._add_next_subtask_to_client_mock(mock_client)
        subtask2 = await self.rtm.get_next_subtask(
            task_id,
            self._get_computing_node(node_id='testnodeid2'),
        )
        subtask_ids = [subtask.subtask_id, subtask2.subtask_id]
        mock_client.discard_subtasks.return_value = subtask_ids

        discarded_subtask_ids = await self.rtm.discard_subtasks(
            task_id,
            subtask_ids,
        )

        assert discarded_subtask_ids == subtask_ids
        for subtask_id in discarded_subtask_ids:
            row = RequestedSubtask.get(
                RequestedSubtask.task == task_id,
                RequestedSubtask.subtask_id == subtask_id)
            assert row.status == SubtaskStatus.cancelled

    async def _start_task(self, **golem_params):
        task_id = await self._create_task(**golem_params)
        await self.rtm.init_task(task_id)
        self.rtm.start_task(task_id)
        return task_id

    @pytest.mark.asyncio
    async def test_stop(self, mock_client):
        # given
        task_id = await self._create_task()
        await self.rtm.init_task(task_id)

        # when
        await self.rtm.stop()

        # then
        mock_client.shutdown.assert_called_once_with()
        assert not self.rtm._app_clients

    def _build_golem_params(
            self,
            resources=None,
            task_timeout=1,
            subtask_timeout=1
    ) -> CreateTaskParams:
        return CreateTaskParams(
            app_id='a',
            name='a',
            task_timeout=task_timeout,
            subtask_timeout=subtask_timeout,
            output_directory=self.tmp_path / 'output',
            resources=resources or [],
            max_subtasks=1,
            max_price_per_hour=1,
            concent_enabled=False,
        )

    async def _create_task(self, **golem_params):
        golem_params = self._build_golem_params(**golem_params)
        app_params = {}
        task_id = await self.rtm.create_task(golem_params, app_params)
        return task_id

    @staticmethod
    def _add_next_subtask_to_client_mock(client_mock):
        result = Subtask(params={}, resources=[])
        client_mock.next_subtask.return_value = result
        client_mock.has_pending_subtasks.return_value = True

    @staticmethod
    def _get_computing_node(node_id='testnodeid') -> ComputingNodeDefinition:
        return ComputingNodeDefinition(
            node_id=node_id,
            name='testnodename',
        )
