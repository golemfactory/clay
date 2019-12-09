# pylint: disable=too-many-ancestors
import asyncio
import os
import uuid
from datetime import datetime
from pathlib import Path
from unittest import mock
from unittest.mock import Mock, call

from twisted.internet.defer import inlineCallbacks

from golem.client import Client
from golem.core.deferred import deferred_from_future
from golem.ethereum import fundslocker, transactionsystem
from golem.task import requestedtaskmanager
from golem.task import taskserver
from golem.task import rpc
from golem.task.taskstate import SubtaskStatus, TaskStatus
from golem.testutils import DatabaseFixture
from tests.factories.task import requestedtaskmanager as rtm_factory
from tests.utils.asyncio import AsyncMock, TwistedAsyncioTestCase


class TaskApiBase(DatabaseFixture):

    def setUp(self):
        super().setUp()

        client = Mock(spec=Client)
        client.has_assigned_task.return_value = False
        client.transaction_system = Mock(
            spec=transactionsystem.TransactionSystem)
        client.transaction_system.get_available_gnt.return_value = 1000
        client.transaction_system.get_available_eth.return_value = 1000
        client.transaction_system.eth_for_batch_payment.return_value = 10
        client.concent_service = Mock()
        client.concent_service.available.return_value = False
        client.task_server = Mock(spec=taskserver.TaskServer)
        client.funds_locker = Mock(spec=fundslocker.FundsLocker)

        self.requested_task_manager = Mock(
            spec=requestedtaskmanager.RequestedTaskManager)
        self.client = client
        self.client.task_server.requested_task_manager = \
            self.requested_task_manager
        self.rpc = rpc.ClientProvider(self.client)

    def get_golem_params(self):
        return {
            'app_id': 'testappid',
            'name': 'testname',
            'output_directory': self.tempdir,
            'resources': [
                os.path.join(self.tempdir, 'resource1'),
                os.path.join(self.tempdir, 'resource2'),
            ],
            'max_price_per_hour': 123,
            'max_subtasks': 4,
            'task_timeout': 60,
            'subtask_timeout': 60,
        }


class TestTaskApiCreate(TwistedAsyncioTestCase, TaskApiBase):

    def setUp(self):
        TwistedAsyncioTestCase.setUp(self)
        TaskApiBase.setUp(self)

        self.task_id = 'test_task_id'

        create_future = asyncio.Future()
        create_future.set_result(self.task_id)
        init_future = asyncio.Future()
        init_future.set_result(None)

        self.requested_task_manager.create_task.return_value = create_future
        self.requested_task_manager.init_task.return_value = init_future

    @inlineCallbacks
    def test_success(self):
        app_params = {
            'app_param1': 'value1',
            'app_param2': 'value2',
        }
        golem_params = self.get_golem_params()
        task_id = self.task_id

        new_task_id, _ = yield self.rpc.create_task({
            'golem': golem_params,
            'app': app_params,
        })
        self.assertEqual(task_id, new_task_id)
        self.requested_task_manager.create_task.assert_called_once_with(
            mock.ANY,
            app_params,
        )
        create_task_params = \
            self.requested_task_manager.create_task.call_args[0][0]
        self.assertEqual(
            golem_params['app_id'],
            create_task_params.app_id,
        )
        self.assertEqual(
            golem_params['name'],
            create_task_params.name,
        )
        self.assertEqual(
            Path(golem_params['output_directory']),
            create_task_params.output_directory,
        )
        self.assertEqual(
            [Path(r) for r in golem_params['resources']],
            create_task_params.resources,
        )
        self.assertEqual(
            golem_params['max_price_per_hour'],
            create_task_params.max_price_per_hour,
        )
        self.assertEqual(
            golem_params['max_subtasks'],
            create_task_params.max_subtasks,
        )
        self.assertEqual(
            golem_params['task_timeout'],
            create_task_params.task_timeout,
        )
        self.assertEqual(
            golem_params['subtask_timeout'],
            create_task_params.subtask_timeout,
        )
        self.assertEqual(
            False,
            create_task_params.concent_enabled,
        )
        self.client.funds_locker.lock_funds.assert_called_once_with(
            task_id,
            golem_params['max_price_per_hour'],
            golem_params['max_subtasks'],
        )

        self.requested_task_manager.init_task.assert_called_once_with(task_id)
        self.client.update_setting.assert_called_once_with(
            'accept_tasks', False, False)

    @inlineCallbacks
    def test_has_assigned_task(self):
        self.client.has_assigned_task.return_value = True

        with self.assertRaises(RuntimeError):
            yield self.rpc._create_task_api_task(self.get_golem_params(), {})

        self.requested_task_manager.create_task.assert_not_called()
        self.requested_task_manager.init_task.assert_not_called()
        self.client.funds_locker.lock_funds.assert_not_called()

    @inlineCallbacks
    def test_failed_init(self):
        self.requested_task_manager.init_task = Exception

        task_id, _ = yield self.rpc.create_task({
            'golem': self.get_golem_params(),
            'app': {},
        })

        self.client.funds_locker.remove_task.assert_called_once_with(task_id)
        self.requested_task_manager.start_task.assert_not_called()
        self.client.update_setting.assert_has_calls((
            call('accept_tasks', False, False),
            call('accept_tasks', True, False)
        ))


class TestTaskOperations(TwistedAsyncioTestCase, TaskApiBase):

    def setUp(self):
        TaskApiBase.setUp(self)
        TwistedAsyncioTestCase.setUp(self)

        self.requested_task_manager = requestedtaskmanager.RequestedTaskManager(
            env_manager=Mock(),
            app_manager=Mock(),
            public_key=os.urandom(32),
            root_path=Path(self.tempdir))
        self.requested_task_manager._finish_subtask = Mock()
        self.requested_task_manager._shutdown_app_client = AsyncMock()
        self.requested_task_manager._get_app_client = AsyncMock(
            return_value=rtm_factory.MockRequestorAppClient())
        self.client.task_server.requested_task_manager = \
            self.requested_task_manager

        # use TestCase.patch instead of unittest.mock.patch for TwistedTestCase
        self.patch(requestedtaskmanager, 'shutil', mock.Mock())

    @inlineCallbacks
    def test_restart_task(self):
        rtm = self.requested_task_manager
        task_id = yield self._create_task()

        assert len(rtm.get_requested_task_ids()) == 1
        assert rtm.get_requested_task(task_id).status is TaskStatus.waiting

        yield self.rpc.restart_task(task_id)
        assert rtm.get_requested_task(task_id).status is TaskStatus.aborted
        assert len(rtm.get_requested_task_ids()) == 2

    @inlineCallbacks
    def test_restart_task_not_enough_funds(self):
        task_id = yield self._create_task()

        ts = self.client.transaction_system
        ts.get_available_gnt.return_value = 0
        ts.get_available_eth.return_value = 0

        new_task_id, error = yield self.rpc.restart_task(task_id)
        assert new_task_id is None
        assert 'Not enough funds' in error

    @inlineCallbacks
    def test_restart_subtasks(self):
        rtm = self.requested_task_manager
        task_id = yield self._create_task()

        for _ in range(3):
            sd = yield deferred_from_future(
                rtm.get_next_subtask(task_id, self._create_computing_node()))
            assert isinstance(sd, requestedtaskmanager.SubtaskDefinition)
            assert rtm.subtask_exists(sd.subtask_id)

        for subtask in rtm.get_requested_task_subtasks(task_id):
            assert subtask.status is SubtaskStatus.starting

        subtask_ids = rtm.get_requested_task_subtask_ids(task_id)
        assert len(subtask_ids) == 3
        result = yield self.rpc.restart_subtasks(task_id, subtask_ids)

        assert result is None
        for subtask in rtm.get_requested_task_subtasks(task_id):
            assert subtask.status is SubtaskStatus.restarted

    @inlineCallbacks
    def test_restart_subtasks_not_enough_funds(self):
        rtm = self.requested_task_manager
        task_id = yield self._create_task()

        for _ in range(3):
            sd = yield deferred_from_future(
                rtm.get_next_subtask(task_id, self._create_computing_node()))
            assert isinstance(sd, requestedtaskmanager.SubtaskDefinition)
            assert rtm.subtask_exists(sd.subtask_id)

        ts = self.client.transaction_system
        ts.get_available_gnt.return_value = 0
        ts.get_available_eth.return_value = 0

        subtask_ids = rtm.get_requested_task_subtask_ids(task_id)
        result = yield self.rpc.restart_subtasks(task_id, subtask_ids)
        assert "Not enough funds" in result

    @inlineCallbacks
    def test_abort_subtask(self):
        rtm = self.requested_task_manager
        task_id = yield self._create_task()

        for _ in range(3):
            sd = yield deferred_from_future(
                rtm.get_next_subtask(task_id, self._create_computing_node()))
            assert isinstance(sd, requestedtaskmanager.SubtaskDefinition)
            yield deferred_from_future(rtm.abort_subtask(sd.subtask_id))

        subtask_ids = rtm.get_requested_task_subtask_ids(task_id)
        for subtask_id in subtask_ids:
            subtask = rtm.get_requested_subtask(subtask_id)
            assert subtask.status == SubtaskStatus.cancelled

    @inlineCallbacks
    def _create_task(self):
        # we need to wait for _init_task_api_task
        with mock.patch.object(self.rpc, '_init_task_api_task'):
            task_id, _ = yield self.rpc.create_task({
                'golem': self.get_golem_params(),
                'app': {},
            })
        yield self.rpc._init_task_api_task(task_id)
        return task_id

    @staticmethod
    def _create_subtask_definition(*_):
        return requestedtaskmanager.SubtaskDefinition(
            subtask_id=str(uuid.uuid4()),
            resources=['input_1', 'input_2'],
            params={},
            deadline=int(datetime.now().timestamp() + 3600.),
        )

    @staticmethod
    def _create_computing_node():
        return requestedtaskmanager.ComputingNodeDefinition(
            node_id=str(uuid.uuid4()),
            name=str(uuid.uuid4()))
