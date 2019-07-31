import random
import unittest.mock as mock

from pydispatch import dispatcher

from golem.monitor.test_helper import MonitorTestBaseClass
from golem.task.taskcomputer import TaskComputerAdapter


class TestTaskComputerSnapshotModel(MonitorTestBaseClass):

    def test_channel(self):
        compute_tasks = random.random() > 0.5
        computer_mock = mock.Mock(
            spec=TaskComputerAdapter,
            compute_tasks=compute_tasks
        )
        computer_mock.has_assigned_task.return_value = True
        computer_mock.assigned_subtask_id = 'test_subtask_id'

        with mock.patch('golem.monitor.monitor.SenderThread.send') as mock_send:
            dispatcher.send(
                signal='golem.monitor',
                event='task_computer_snapshot',
                task_computer=computer_mock,
            )
            self.assertEqual(mock_send.call_count, 1)
            result = mock_send.call_args[0][0].dict_repr()
            for key in ('cliid', 'sessid', 'timestamp'):
                del result[key]
            self.maxDiff = None
            expected = {
                'type': 'TaskComputer',
                'compute_task': compute_tasks,
                'assigned_subtask': 'test_subtask_id',
            }
            self.assertEqual(expected, result)
