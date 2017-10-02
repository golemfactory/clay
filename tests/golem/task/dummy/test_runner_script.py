import unittest
import unittest.mock as mock

from golem.network.socketaddress import SocketAddress
from golem.testutils import DatabaseFixture
from tests.golem.task.dummy import runner, task


class TestDummyTaskRunnerScript(DatabaseFixture):
    """Tests for the runner script"""

    @mock.patch('devp2p.app.BaseApp.start')
    @mock.patch("tests.golem.task.dummy.runner.run_requesting_node")
    @mock.patch("tests.golem.task.dummy.runner.run_computing_node")
    @mock.patch("tests.golem.task.dummy.runner.run_simulation")
    def test_runner_dispatch_requesting(
            self, mock_run_simulation, mock_run_computing_node,
            mock_run_requesting_node, *_):
        args = ["runner.py", runner.REQUESTING_NODE_KIND, self.path, "7"]
        runner.dispatch(args)
        self.assertTrue(mock_run_requesting_node.called)
        self.assertEqual(mock_run_requesting_node.call_args[0], (self.path, 7))
        self.assertFalse(mock_run_computing_node.called)
        self.assertFalse(mock_run_simulation.called)

    @mock.patch('devp2p.app.BaseApp.start')
    @mock.patch("tests.golem.task.dummy.runner.run_requesting_node")
    @mock.patch("tests.golem.task.dummy.runner.run_computing_node")
    @mock.patch("tests.golem.task.dummy.runner.run_simulation")
    def test_runner_dispatch_computing(
            self, mock_run_simulation, mock_run_computing_node,
            mock_run_requesting_node, *_):
        args = ["runner.py", runner.COMPUTING_NODE_KIND,
                self.path, "1.2.3.4:5678", "NoBootstrap", "0"]
        runner.dispatch(args)
        self.assertFalse(mock_run_requesting_node.called)
        self.assertTrue(mock_run_computing_node.called)
        self.assertEqual(mock_run_computing_node.call_args[0],
                         (self.path, SocketAddress("1.2.3.4", 5678),
                          "NoBootstrap", 0))
        self.assertEqual(mock_run_computing_node.call_args[1],
                         {"fail_after": None})
        self.assertFalse(mock_run_simulation.called)

    @mock.patch('devp2p.app.BaseApp.start')
    @mock.patch("tests.golem.task.dummy.runner.run_requesting_node")
    @mock.patch("tests.golem.task.dummy.runner.run_computing_node")
    @mock.patch("tests.golem.task.dummy.runner.run_simulation")
    def test_runner_dispatch_computing_with_failure(
            self, mock_run_simulation, mock_run_computing_node,
            mock_run_requesting_node, *_):
        args = ["runner.py", runner.COMPUTING_NODE_KIND,
                self.path, "10.0.255.127:16000", "NoBootstrap", "0", "25"]
        runner.dispatch(args)
        self.assertFalse(mock_run_requesting_node.called)
        self.assertTrue(mock_run_computing_node.called)
        self.assertEqual(mock_run_computing_node.call_args[0],
                         (self.path, SocketAddress("10.0.255.127", 16000),
                          "NoBootstrap", 0), {"fail_after": 25})
        self.assertEqual(mock_run_computing_node.call_args[1],
                         {"fail_after": 25.0})
        self.assertFalse(mock_run_simulation.called)

    @mock.patch('devp2p.app.BaseApp.start')
    @mock.patch("tests.golem.task.dummy.runner.run_requesting_node")
    @mock.patch("tests.golem.task.dummy.runner.run_computing_node")
    @mock.patch("tests.golem.task.dummy.runner.run_simulation")
    def test_runner_run_simulation(
            self, mock_run_simulation, mock_run_computing_node,
            mock_run_requesting_node, *_):
        args = ["runner.py"]
        mock_run_simulation.return_value = None
        runner.dispatch(args)
        self.assertFalse(mock_run_requesting_node.called)
        self.assertFalse(mock_run_computing_node.called)
        self.assertTrue(mock_run_simulation.called)

    @mock.patch('gevent.greenlet.Greenlet.join')
    @mock.patch('devp2p.app.BaseApp.start')
    @mock.patch('devp2p.app.BaseApp.stop')
    @mock.patch('golem.core.common.config_logging')
    @mock.patch("golem.client.Client.enqueue_new_task")
    @mock.patch("tests.golem.task.dummy.runner.install_event_loop",
                return_value=(mock.Mock(), mock.Mock()))
    def test_run_requesting_node(self, mock_reactor, enqueue_new_task, *_):
        client = runner.run_requesting_node(self.path, 3)
        self.assertTrue(enqueue_new_task.called)
        client.quit()

    @mock.patch('gevent.greenlet.Greenlet')
    @mock.patch('gevent.hub.get_hub')
    @mock.patch('golem.core.common.config_logging')
    @mock.patch("tests.golem.task.dummy.runner.install_event_loop",
                return_value=(mock.Mock(), mock.Mock()))
    def test_run_computing_node(self, *_):
        client = runner.run_computing_node(
            self.path, SocketAddress("127.0.0.1", 20200),
            "84447c7d60f95f7108e85310622d0dbdea61b0763898d6bf3dd60d8954b9c07f9e"
            "0cc156b5397358048000ac4de63c12250bc6f1081780add091e0d3714060e8",
            0
        )
        environments = list(client.environments_manager.environments)
        self.assertTrue(any(env.get_id() == task.DummyTask.ENVIRONMENT_NAME
                            for env in environments))
        client.quit()

    @mock.patch("subprocess.Popen")
    def test_run_simulation(self, mock_popen, *_):
        mock_process = mock.MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process
        mock_process.stdout.readline.return_value = runner.format_msg(
            "REQUESTOR", 12345,
            "Listening on 1.2.3.4:5678 this_enode=enode://84447c7d60f95f7108e85"
            "310622d0dbdea61b0763898d6bf3dd60d8954b9c07f9e0cc156b5397358048000a"
            "c4de63c12250bc6f1081780add091e0d3714060e8@1.2.3.4:5678"
        ).encode()
        runner.run_simulation()
