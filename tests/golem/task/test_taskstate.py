import time
import unittest

from freezegun import freeze_time

from golem.core.common import timeout_to_deadline, deadline_to_timeout, \
    get_timestamp_utc
from golem.task.taskstate import SubtaskState, SubtaskStatus, TaskState, \
    TaskStatus


class TestSubtaskState(unittest.TestCase):

    def test_init(self):
        ss = SubtaskState()
        self.assertIsInstance(ss, SubtaskState)
        ss.results.append(1)
        ss2 = SubtaskState()
        ss2.results.append(2)
        self.assertEqual(ss.results, [1])
        self.assertEqual(ss2.results, [2])

    @staticmethod
    @freeze_time()
    def test_to_dictionary():
        ss = SubtaskState()
        ss.subtask_id = "ABCDEF"
        ss.subtask_progress = 0.92
        ss.time_started = get_timestamp_utc()
        ss.deadline = timeout_to_deadline(ss.time_started + 5)
        ss.extra_data = {"param1": 1323, "param2": "myparam"}
        ss.subtask_rem_time = deadline_to_timeout(ss.deadline) - ss.time_started
        ss.subtask_status = SubtaskStatus.starting
        ss.value = 138
        ss.stdout = "path/to/file"
        ss.stderr = "path/to/file2"
        ss.results = ["path/to/file3", "path/to/file4"]
        ss.computation_time = 130
        ss.node_id = "NODE1"

        ss_dict = ss.to_dictionary()
        assert ss_dict['subtask_id'] == "ABCDEF"
        assert ss_dict['progress'] == 0.92
        assert ss_dict['time_started'] == get_timestamp_utc()

        assert ss_dict.get('deadline') is None
        assert ss_dict.get('extra_data') is None

        assert ss_dict['time_remaining'] == 5
        assert ss_dict['status'] == SubtaskStatus.starting.value

        assert ss_dict.get('value') is None

        assert ss_dict['stdout'] == "path/to/file"
        assert ss_dict['stderr'] == "path/to/file2"
        assert ss_dict['results'] == ["path/to/file3", "path/to/file4"]

        assert ss_dict.get('computation_time') is None
        assert ss_dict['node_id'] == "NODE1"


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
