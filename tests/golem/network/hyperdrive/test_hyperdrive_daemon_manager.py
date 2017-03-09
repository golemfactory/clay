import os

from mock import patch, Mock
from requests import ConnectionError

from golem.network.hyperdrive.daemon_manager import HyperdriveDaemonManager
from golem.testutils import TempDirFixture


class TestHyperdriveDaemonManager(TempDirFixture):

    @patch('golem.core.processmonitor.ProcessMonitor.start')
    @patch('golem.core.processmonitor.ProcessMonitor.add_callbacks')
    @patch('golem.core.processmonitor.ProcessMonitor.add_child_processes')
    @patch('atexit.register')
    def test_start(self, register, *_):

        dest_dir = os.path.join(self.path, HyperdriveDaemonManager._executable)
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)

        with patch('os.makedirs') as makedirs:
            daemon_manager = HyperdriveDaemonManager(self.path)
            assert not makedirs.called

        daemon_manager._monitor.add_callbacks.assert_called_with(daemon_manager._start)
        register.assert_called_with(daemon_manager.stop)

        process = Mock()

        def _running(val=True):
            daemon_manager._daemon_running = lambda *_: val

        _running(False)
        process.poll.return_value = True
        daemon_manager._monitor.add_child_processes.called = False

        with patch('time.sleep', side_effect=lambda *_: _running(True)), \
             patch('subprocess.Popen', return_value=process):

            with self.assertRaises(RuntimeError):
                daemon_manager.start()
            assert daemon_manager._monitor.start.called
            assert not daemon_manager._monitor.add_child_processes.called

        _running(False)
        process.poll.return_value = None
        daemon_manager._monitor.add_child_processes.called = False

        with patch('time.sleep', side_effect=lambda *_: _running(True)), \
             patch('subprocess.Popen', return_value=process):

            daemon_manager.start()
            assert daemon_manager._monitor.start.called
            daemon_manager._monitor.add_child_processes.assert_called_with(process)

    def test_daemon_running(self):

        with patch('os.makedirs') as makedirs:
            daemon_manager = HyperdriveDaemonManager(self.path)
            assert makedirs.called

        def raise_exc():
            raise ConnectionError()

        with patch('golem.network.hyperdrive.client.HyperdriveClient.id',
                   side_effect=raise_exc):
            assert not daemon_manager._daemon_running()

        with patch('golem.network.hyperdrive.client.HyperdriveClient.id',
                   side_effect=lambda *_: '0xdeadbeef'):
            assert daemon_manager._daemon_running()

