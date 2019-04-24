from unittest import mock

from golem.network.transport.tcpnetwork import SocketAddress
from golem.testutils import DatabaseFixture
from tests.golem.task.dummy import runner, task


class TestDummyTaskRunnerScript(DatabaseFixture):
    """Tests for the runner script"""

    @mock.patch("tests.golem.task.dummy.runner.run_requesting_node")
    @mock.patch("tests.golem.task.dummy.runner.run_computing_node")
    @mock.patch("tests.golem.task.dummy.runner.run_simulation")
    def test_runner_dispatch_requesting(
            self, mock_run_simulation, mock_run_computing_node,
            mock_run_requesting_node):
        args = ["runner.py", runner.REQUESTING_NODE_KIND, self.path, "7"]
        runner.dispatch(args)
        self.assertTrue(mock_run_requesting_node.called)
        self.assertEqual(mock_run_requesting_node.call_args[0], (self.path, 7))
        self.assertFalse(mock_run_computing_node.called)
        self.assertFalse(mock_run_simulation.called)

    @mock.patch("tests.golem.task.dummy.runner.run_requesting_node")
    @mock.patch("tests.golem.task.dummy.runner.run_computing_node")
    @mock.patch("tests.golem.task.dummy.runner.run_simulation")
    def test_runner_dispatch_computing(
            self, mock_run_simulation, mock_run_computing_node,
            mock_run_requesting_node):
        args = ["runner.py", runner.COMPUTING_NODE_KIND,
                self.path, "1.2.3.4:5678", "pid", ]
        runner.dispatch(args)
        mock_run_requesting_node.assert_not_called()
        mock_run_computing_node.assert_called_once_with(
            self.path,
            SocketAddress("1.2.3.4", 5678),
            fail_after=None,
            provider_id="pid",
        )
        mock_run_simulation.assert_not_called()

    @mock.patch("tests.golem.task.dummy.runner.run_requesting_node")
    @mock.patch("tests.golem.task.dummy.runner.run_computing_node")
    @mock.patch("tests.golem.task.dummy.runner.run_simulation")
    def test_runner_dispatch_computing_with_failure(
            self, mock_run_simulation, mock_run_computing_node,
            mock_run_requesting_node):
        args = ["runner.py", runner.COMPUTING_NODE_KIND,
                self.path, "10.0.255.127:16000", "pid", "25"]
        runner.dispatch(args)
        mock_run_requesting_node.assert_not_called()
        mock_run_computing_node.assert_called_once_with(
            self.path,
            SocketAddress("10.0.255.127", 16000),
            fail_after=25.0,
            provider_id='pid'
        )
        mock_run_simulation.assert_not_called()

    @mock.patch("tests.golem.task.dummy.runner.run_requesting_node")
    @mock.patch("tests.golem.task.dummy.runner.run_computing_node")
    @mock.patch("tests.golem.task.dummy.runner.run_simulation")
    def test_runner_run_simulation(
            self, mock_run_simulation, mock_run_computing_node,
            mock_run_requesting_node):
        args = ["runner.py"]
        mock_run_simulation.return_value = None
        runner.dispatch(args)
        self.assertFalse(mock_run_requesting_node.called)
        self.assertFalse(mock_run_computing_node.called)
        self.assertTrue(mock_run_simulation.called)

    @mock.patch(
        "golem.network.concent.handlers_library"
        ".HandlersLibrary.register_handler",
    )
    @mock.patch("tests.golem.task.dummy.runner.atexit")
    @mock.patch("golem.core.common.config_logging")
    @mock.patch("golem.task.rpc.enqueue_new_task")
    @mock.patch("tests.golem.task.dummy.runner.reactor")
    def test_run_requesting_node(self, mock_reactor,
                                 mock_enqueue_new_task,
                                 mock_config_logging, *_):
        client = runner.run_requesting_node(self.path, 3)
        self.assertTrue(mock_reactor.run.called)
        self.assertTrue(mock_enqueue_new_task.called)
        self.assertTrue(mock_config_logging.called)
        client.quit()

    @mock.patch("tests.golem.task.dummy.runner.atexit")
    @mock.patch("tests.golem.task.dummy.runner.reactor")
    @mock.patch("golem.core.common.config_logging")
    def test_run_computing_node(self, mock_config_logging, mock_reactor, _):
        client = runner.run_computing_node(
            self.path,
            SocketAddress("127.0.0.1", 40102),
            "pid",
        )
        assert task.DummyTask.ENVIRONMENT_NAME in \
            client.environments_manager.environments
        mock_reactor.run.assert_called_once_with()
        mock_config_logging.assert_called_once_with(
            datadir=mock.ANY,
            loglevel='DEBUG',
            formatter_prefix="Ppid ",
        )
        client.quit()

    @mock.patch("subprocess.Popen")
    def test_run_simulation(self, mock_popen):
        mock_process = mock.MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process
        mock_process.stdout.readline.return_value = runner.format_msg(
            "REQUESTOR", mock_process.pid, "Listening on 1.2.3.4:5678").encode()
        runner.run_simulation()
        self.assertTrue(mock_popen.called)
