import mock
from pydispatch import dispatcher
import random

from golem.monitor.test_helper import MonitorTestBaseClass

class TestTaskComputerSnapshotModel(MonitorTestBaseClass):
    def test_channel(self):
        computer_mock = mock.MagicMock()
        computer_mock.waiting_for_task = waiting_for_task = random.random() > 0.5
        computer_mock.counting_task = counting_task = random.random() > 0.5
        computer_mock.task_requested = task_requested = random.random() > 0.5
        computer_mock.compute_tasks = compute_tasks = random.random() > 0.5
        computer_mock.assigned_subtasks = assigned_subtasks = dict((x, None) for x in range(100))

        with mock.patch('golem.monitor.monitor.SenderThread.send') as mock_send:
            dispatcher.send(
                signal='golem.monitor',
                event='task_computer_snapshot',
                task_computer=computer_mock,
            )
            self.assertEquals(mock_send.call_count, 1)
            result = mock_send.call_args[0][0].dict_repr()
            for key in ('cliid', 'sessid', 'timestamp'):
                del result[key]
            self.maxDiff = None
            expected = {
                'type': 'TaskComputer',
                'waiting_for_task': waiting_for_task,
                'task_requested': task_requested,
                'counting_task': counting_task,
                'compute_task': compute_tasks,
                'assigned_subtasks': assigned_subtasks.keys(),
            }
            self.assertEquals(expected, result)
