import unittest
import pytest

from tests.golem.task.dummy import runner


@pytest.mark.slow
class TestDummyTask(unittest.TestCase):
    """Tests for the dummy task computation using the runner script"""

    def test_dummy_task_computation(self):
        error_msg = runner.run_simulation(
            num_computing_nodes=2, num_subtasks=3)
        self.assertIn(error_msg, [None, "Node exited with return code 0"])

    def test_dummy_task_computation_timeout(self):
        error_msg = runner.run_simulation(timeout=5)
        self.assertEqual(error_msg, "Computation timed out")

    def test_dummy_task_computation_subprocess_error(self):
        # Make the first computing node fail after approx. 5 secs
        error_msg = runner.run_simulation(
            num_computing_nodes=2, num_subtasks=10, timeout=240,
            node_failure_times=[5])
        self.assertTrue(error_msg.startswith("Node exited with return code"))
