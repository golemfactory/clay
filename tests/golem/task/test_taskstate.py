import time
import unittest

from golem.core.common import timeout_to_deadline, deadline_to_timeout, \
    get_timestamp_utc
from golem.task.taskstate import SubtaskState, SubtaskStatus


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
    def test_to_dictionary():
        ss = SubtaskState()
        ss.subtask_definition = "My long task definition"
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
        ss.computer.node_name = "NODE1"
        ss.computer.node_id = "abc131"
        ss.computer.performance = 180
        ss.computer.ip_address = "10.10.10.1"
        ss.computer.port = 1311

        ss_dict = ss.to_dictionary()
        assert ss_dict['description'] == "My long task definition"
        assert ss_dict['subtask_id'] == "ABCDEF"
        assert ss_dict['progress'] == 0.92
        assert ss_dict['time_started'] <= time.time()

        assert ss_dict.get('deadline') is None
        assert ss_dict.get('extra_data') is None

        assert ss_dict['time_remaining'] <= 5
        assert ss_dict['status'] == SubtaskStatus.starting

        assert ss_dict.get('value') is None

        assert ss_dict['stdout'] == "path/to/file"
        assert ss_dict['stderr'] == "path/to/file2"
        assert ss_dict['results'] == ["path/to/file3", "path/to/file4"]

        assert ss_dict.get('computation_time') is None

        assert ss_dict['node_name'] == "NODE1"
        assert ss_dict['node_id'] == "abc131"
        assert ss_dict['node_performance'] == "180"
        assert ss_dict['node_ip_address'] == "10.10.10.1"
        assert ss_dict['node_port'] == 1311
