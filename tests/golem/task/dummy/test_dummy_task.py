import runner
from golem.tools.testwithappconfig import TestWithAppConfig


class TestDummyTask(TestWithAppConfig):
    """Tests for the dummy task computation using the runner script"""

    @classmethod
    def setUpClass(cls):
        super(TestDummyTask, cls).setUpClass()
        runner.run_simulation(
            num_computing_nodes=2, num_subtasks=3, timeout=12,
            node_failure_times=[6]
        )

    def test_dummy_task_computation(self, *mocks):
        error_msg = runner.run_simulation(
            num_computing_nodes=2, num_subtasks=3, timeout=120)
        self.assertIsNone(error_msg)

    def test_dummy_task_computation_timeout(self, *mocks):
        error_msg = runner.run_simulation(timeout=1)
        self.assertEqual(error_msg, "Computation timed out")

    def test_dummy_task_computation_subprocess_error(self, *mocks):
        # Make the first computing node fail after approx. 5 secs
        error_msg = runner.run_simulation(
            num_computing_nodes=2, num_subtasks=10, timeout=120,
            node_failure_times=[5])
        self.assertTrue(error_msg.startswith("Node exited with return code"))
