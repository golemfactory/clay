import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from mock import Mock, call

from golem.client import Client
from golem.ethereum import fundslocker, transactionsystem
from golem.task import requestedtaskmanager
from golem.task import taskserver
from golem.task import rpc


class TestTaskApiCreate(unittest.TestCase):
    def setUp(self):
        self.client = Mock(spec=Client)
        self.client.transaction_system = Mock(
            spec=transactionsystem.TransactionSystem,
        )
        self.client.transaction_system.get_available_gnt.return_value = 1000
        self.client.transaction_system.get_available_eth.return_value = 1000
        self.client.transaction_system.eth_for_batch_payment.return_value = 10

        self.client.concent_service = Mock()
        self.client.concent_service.available.return_value = False

        self.requested_task_manager = Mock(
            spec=requestedtaskmanager.RequestedTaskManager,
        )
        self.client.task_server = Mock(spec=taskserver.TaskServer)
        self.client.task_server.requested_task_manager = \
            self.requested_task_manager

        self.client.funds_locker = Mock(spec=fundslocker.FundsLocker)

        self.rpc = rpc.ClientProvider(self.client)

    @staticmethod
    def get_golem_params():
        random_dir = tempfile.gettempdir()
        return {
            'app_id': 'testappid',
            'name': 'testname',
            'output_directory': random_dir,
            'resources': [
                os.path.join(random_dir, 'resource1'),
                os.path.join(random_dir, 'resource2'),
            ],
            'max_price_per_hour': 123,
            'max_subtasks': 4,
            'task_timeout': 60,
            'subtask_timeout': 60,
        }

    def test_success(self):
        task_params = {
            'app_param1': 'value1',
            'app_param2': 'value2',
        }
        golem_params = self.get_golem_params()
        task_id = 'test_task_id'
        self.requested_task_manager.create_task.return_value = task_id

        new_task_id = self.rpc.create_task_api_task(task_params, golem_params)
        self.assertEqual(task_id, new_task_id)
        self.requested_task_manager.create_task.assert_called_once_with(
            mock.ANY,
            task_params,
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
            'accept_tasks', False)

    def test_failed_init(self):
        self.requested_task_manager.init_task.side_effect = Exception

        task_id = self.rpc.create_task_api_task({}, self.get_golem_params())

        self.client.funds_locker.remove_task.assert_called_once_with(task_id)
        self.requested_task_manager.start_task.assert_not_called()
        self.client.update_setting.assert_has_calls((
            call('accept_tasks', False),
            call('accept_tasks', True)
        ))
