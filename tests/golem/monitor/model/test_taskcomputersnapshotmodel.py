import random
import unittest.mock as mock

from golem.monitor.test_helper import MonitorTestBaseClass
from golem.task.taskcomputer import TaskComputerAdapter


class TestTaskComputerSnapshotModel(MonitorTestBaseClass):
    maxDiff = None

    @mock.patch('requests.post')
    @mock.patch('json.dumps')
    def test_channel(self, mock_dumps, *_):
        compute_tasks = random.random() > 0.5
        computer_mock = mock.Mock(
            spec=TaskComputerAdapter,
            compute_tasks=compute_tasks
        )
        computer_mock.has_assigned_task.return_value = True
        computer_mock.assigned_subtask_id = 'test_subtask_id'

        self.loop.run_until_complete(self.monitor.on_task_computer_snapshot(
            task_computer=computer_mock,
        ))
        mock_dumps.assert_called_once()
        result = mock_dumps.call_args[0][0]
        self.maxDiff = None
        expected = {
            'proto_ver': 1,
            'data': {
                'cliid': mock.ANY,
                'sessid': mock.ANY,
                'timestamp': mock.ANY,

                'type': 'TaskComputer',
                'compute_task': compute_tasks,
                'assigned_subtask': 'test_subtask_id',
            },
        }
        self.assertCountEqual(expected, result)
