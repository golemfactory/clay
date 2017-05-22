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

        def ports(*_):
            return dict(
                UTP=dict(
                    address='0.0.0.0',
                    port=3282
                ),
                TCP=dict(
                    address='0.0.0.0',
                    port=3282
                )
            )

        def none(*_):
            pass

        process = Mock()
        process.poll.return_value = None

        daemon_manager = HyperdriveDaemonManager(self.path)
        daemon_manager._monitor.add_callbacks.assert_called_with(daemon_manager._start)
        # only registered atexit function is monitor.exit
        register.assert_called_with(daemon_manager._monitor.exit)
        assert register.call_count == 1

        # hyperdrive not running
        process.poll.return_value = True
        daemon_manager._monitor.add_child_processes.called = False

        with patch.object(daemon_manager, 'addresses', side_effect=none), \
             patch('subprocess.Popen', return_value=process), \
             patch('os.makedirs') as makedirs:

            with self.assertRaises(RuntimeError):
                daemon_manager.start()

            register.assert_called_with(daemon_manager.stop)

            assert register.call_count == 2
            assert daemon_manager._monitor.start.called
            assert makedirs.called
            assert not daemon_manager._monitor.add_child_processes.called

        process.poll.return_value = None
        daemon_manager._monitor.add_child_processes.called = False

        with patch.object(daemon_manager, 'addresses', side_effect=none), \
             patch('subprocess.Popen', return_value=process), \
             patch('os.makedirs') as makedirs:

            daemon_manager.start()

            register.assert_called_with(daemon_manager.stop)
            assert register.call_count == 3
            assert daemon_manager._monitor.start.called
            assert makedirs.called
            daemon_manager._monitor.add_child_processes.assert_called_with(process)

        # hyperdrive is running
        process.poll.return_value = True
        daemon_manager._monitor.add_child_processes.called = False

        with patch.object(daemon_manager, 'addresses', side_effect=ports), \
             patch('subprocess.Popen', return_value=process), \
             patch('os.makedirs') as makedirs:

            daemon_manager.start()

            register.assert_called_with(daemon_manager.stop)
            assert register.call_count == 4
            assert daemon_manager._monitor.start.called
            assert not makedirs.called
            assert not daemon_manager._monitor.add_child_processes.called

    def test_daemon_running(self):

        daemon_manager = HyperdriveDaemonManager(self.path)

        def raise_exc():
            raise ConnectionError()

        with patch('golem.network.hyperdrive.client.HyperdriveClient.addresses',
                   side_effect=raise_exc):
            assert not daemon_manager.addresses()

        with patch('golem.network.hyperdrive.client.HyperdriveClient.addresses',
                   side_effect=lambda *_: {'TCP': {'port': 1234}}):
            assert daemon_manager.addresses()

