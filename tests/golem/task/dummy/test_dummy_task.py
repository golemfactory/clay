import mock

import runner
from golem.tools.testwithappconfig import TestWithAppConfig


#  @mock.patch('golem.transactions.incomeskeeper.IncomesDatabase')
class TestDummyTask(TestWithAppConfig):

    def test_dummy_task_computation(self, *mocks):
        error_msg = runner.run_simulation(
            num_computing_nodes=2, num_subtasks=3, timeout=120)
        self.assertIsNone(error_msg)

    def test_dummy_task_computation_timeout(self, *mocks):
        error_msg = runner.run_simulation(timeout=1)
        self.assertEqual(error_msg, "Computation timed out")

    @mock.patch('subprocess.Popen')
    @mock.patch('re.compile')
    def test_dummy_task_computation_subprocess_error(self, *mocks):
        error_msg = runner.run_simulation(
            num_computing_nodes=2, num_subtasks=4, timeout=60)
        self.assertTrue(error_msg.startswith("Node exited with return code"))
