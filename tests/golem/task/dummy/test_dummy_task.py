import runner
import unittest


class TestDummyTask(unittest.TestCase):
    """Tests for the dummy task computation using the runner script"""

    def test_dummy_task_computation(self, *mocks):
        error_msg = runner.run_simulation(
            num_computing_nodes=2, num_subtasks=3, timeout=420)
        self.assertIsNone(error_msg)

    def test_dummy_task_computation_timeout(self, *mocks):
        error_msg = runner.run_simulation(timeout=5)
        self.assertEqual(error_msg, "Computation timed out")

    def test_dummy_task_computation_subprocess_error(self, *mocks):
        # Make the first computing node fail after approx. 5 secs
        error_msg = runner.run_simulation(
            num_computing_nodes=2, num_subtasks=10, timeout=120,
            node_failure_times=[5])
        self.assertTrue(error_msg.startswith("Node exited with return code"))
