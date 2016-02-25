import unittest
import mock

import runner
from golem.tools.testwithappconfig import TestWithAppConfig


class TestDummyTask(TestWithAppConfig):

    def test_dummy_task_computation(self):
        runner.run_nodes(num_computing_nodes = 2, num_subtasks = 4, timeout= 60)
        self.assertIsNone(runner.computation_error)

    def test_dummy_task_computation_timeout(self):
        runner.run_nodes(timeout = 1)
        self.assertEqual(runner.computation_error, "Task computation timed out")

    @mock.patch('subprocess.Popen')
    def test_dummy_task_computation_subprocess_error(self, mock_popen):
        runner.run_nodes(num_computing_nodes = 2, num_subtasks = 4, timeout= 60)
        self.assertTrue(
            runner.computation_error.startswith("Computing process exited"))
