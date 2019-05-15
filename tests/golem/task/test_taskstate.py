import datetime
import time
import unittest

from freezegun import freeze_time

from golem.core.common import timeout_to_deadline
from golem.task.taskstate import SubtaskState, SubtaskStatus, TaskState, \
    TaskStatus


class TestSubtaskState(unittest.TestCase):
    @freeze_time(datetime.datetime(2019, 12, 12, 0, 0, 0))
    def test_to_dictionary(self):
        time_started = int(time.time())
        deadline = timeout_to_deadline(time_started + 5)
        extra_data = {"param1": 1323, "param2": "myparam"}
        ss = SubtaskState(
            subtask_id="ABCDEF",
            progress=0.92,
            time_started=time_started,
            deadline=deadline,
            extra_data=extra_data,
            price=138,
            stdout="path/to/file",
            stderr="path/to/file2",
            results=["path/to/file3", "path/to/file4"],
            node_id="NODE1",
        )

        ss_dict = ss.to_dict()
        self.assertCountEqual(
            ss_dict,
            {
                'subtask_id': "ABCDEF",
                'progress': 0.92,
                'time_started': time_started,
                'deadline': deadline,
                'extra_data': extra_data,
                'status': SubtaskStatus.starting.value,
                'stdout': "path/to/file",
                'stderr': "path/to/file2",
                'results': ["path/to/file3", "path/to/file4"],
                'node_id': "NODE1",
                'node_name': "",
                'price': 138,
            },
        )



class TestTaskState(unittest.TestCase):

    @freeze_time(as_arg=True)
    def test_last_update_time(  # pylint: disable=no-self-argument
            frozen_time, self):
        ts = TaskState()
        self.assertEqual(ts.last_update_time, time.time())

        frozen_time.tick()  # pylint: disable=no-member

        ts.status = TaskStatus.restarted
        self.assertNotEqual(ts.last_update_time, time.time())

        frozen_time.tick()  # pylint: disable=no-member

        ts.status = TaskStatus.finished
        self.assertEqual(ts.last_update_time, time.time())

        ts_dict = ts.to_dictionary()
        self.assertEqual(ts_dict.get('last_updated'), time.time())
