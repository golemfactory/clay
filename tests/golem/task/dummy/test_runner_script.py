import mock

from golem.network.transport.tcpnetwork import TCPAddress
from golem.tools.testwithappconfig import TestWithAppConfig

import runner
import task


class TestDummyTaskRunnerScript(TestWithAppConfig):
    """Tests for the runner script"""

    @mock.patch("runner.run_requesting_node")
    @mock.patch("runner.run_computing_node")
    @mock.patch("runner.run_simulation")
    def test_runner_dispatch_requesting(
            self, mock_run_simulation, mock_run_computing_node,
            mock_run_requesting_node):
        args = ["runner.py", runner.REQUESTING_NODE_KIND, "7"]
        runner.dispatch(args)
        self.assertTrue(mock_run_requesting_node.called)
        self.assertEqual(mock_run_requesting_node.call_args[0], (7,))
        self.assertFalse(mock_run_computing_node.called)
        self.assertFalse(mock_run_simulation.called)

    @mock.patch("runner.run_requesting_node")
    @mock.patch("runner.run_computing_node")
    @mock.patch("runner.run_simulation")
    def test_runner_dispatch_computing(
            self, mock_run_simulation, mock_run_computing_node,
            mock_run_requesting_node):
        args = ["runner.py", runner.COMPUTING_NODE_KIND, "1.2.3.4:5678"]
        runner.dispatch(args)
        self.assertFalse(mock_run_requesting_node.called)
        self.assertTrue(mock_run_computing_node.called)
        self.assertEqual(mock_run_computing_node.call_args[0],
                         (TCPAddress("1.2.3.4", 5678),))
        self.assertEqual(mock_run_computing_node.call_args[1],
                         {"fail_after": None})
        self.assertFalse(mock_run_simulation.called)

    @mock.patch("runner.run_requesting_node")
    @mock.patch("runner.run_computing_node")
    @mock.patch("runner.run_simulation")
    def test_runner_dispatch_computing_with_failure(
            self, mock_run_simulation, mock_run_computing_node,
            mock_run_requesting_node):
        args = ["runner.py", runner.COMPUTING_NODE_KIND, "1.2.3.4:5678", "25"]
        runner.dispatch(args)
        self.assertFalse(mock_run_requesting_node.called)
        self.assertTrue(mock_run_computing_node.called)
        self.assertEqual(mock_run_computing_node.call_args[0],
                         (TCPAddress("1.2.3.4", 5678),))
        self.assertEqual(mock_run_computing_node.call_args[1],
                         {"fail_after": 25.0})
        self.assertFalse(mock_run_simulation.called)

    @mock.patch("runner.run_requesting_node")
    @mock.patch("runner.run_computing_node")
    @mock.patch("runner.run_simulation")
    def test_runner_run_simulation(
            self, mock_run_simulation, mock_run_computing_node,
            mock_run_requesting_node):
        args = ["runner.py"]
        mock_run_simulation.return_value = None
        runner.dispatch(args)
        self.assertFalse(mock_run_requesting_node.called)
        self.assertFalse(mock_run_computing_node.called)
        self.assertTrue(mock_run_simulation.called)

    @mock.patch("runner.reactor")
    def test_run_requesting_node(self, mock_reactor):
        client = runner.run_requesting_node(3)
        tasks = client.task_server.task_manager.tasks
        self.assertEqual(len(tasks), 1)
        self.assertIsInstance(tasks.values()[0], task.DummyTask)

    @mock.patch("runner.reactor")
    def test_run_computing_node(self, mock_reactor):
        client = runner.run_computing_node(TCPAddress("127.0.0.1", 40102))
        environments = list(client.environments_manager.environments)
        self.assertTrue(any(env.get_id() == task.DummyTask.ENVIRONMENT_NAME
                            for env in environments))

    @mock.patch("subprocess.Popen")
    def test_run_simulation(self, mock_popen):
        mock_process = mock.MagicMock()
        mock_popen.return_value = mock_process
        mock_process.stdout.readline.return_value = runner.format_msg(
            "REQUESTER", 12345, "Listening on 1.2.3.4:5678")
        runner.run_simulation()
