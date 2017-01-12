import unittest

import runner


class TestDummyTask(unittest.TestCase):
    """Tests for the dummy task computation using the runner script"""

    def test_dummy_task_computation(self, *mocks):
        error_msg = runner.run_simulation(
            num_computing_nodes=2, num_subtasks=3, timeout=300)
        assert error_msg.startswith("Computation finished")

    def test_dummy_task_computation_timeout(self, *mocks):
        error_msg = runner.run_simulation(timeout=5)
        assert error_msg.startswith("Computation timed out")

    def test_dummy_task_computation_subprocess_error(self, *mocks):
        # Make the first computing node fail after approx. 5 secs
        error_msg = runner.run_simulation(
            num_computing_nodes=2, num_subtasks=10, timeout=120,
            node_failure_times=[5])
        assert error_msg.startswith("Node failure")
