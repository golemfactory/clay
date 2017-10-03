from requests import ConnectionError
import unittest.mock as mock

from golem.network.hyperdrive.daemon_manager import HyperdriveDaemonManager
from golem.testutils import TempDirFixture


class TestHyperdriveDaemonManager(TempDirFixture):

    @mock.patch('golem.core.processmonitor.ProcessMonitor.start')
    @mock.patch('golem.core.processmonitor.ProcessMonitor.add_callbacks')
    @mock.patch('golem.core.processmonitor.ProcessMonitor.add_child_processes')
    @mock.patch('atexit.register')
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

        process = mock.Mock()
        process.poll.return_value = None

        daemon_manager = HyperdriveDaemonManager(self.path)
        daemon_manager._monitor.add_callbacks.assert_called_with(daemon_manager._start)

        assert register.call_count == 2
        register.assert_has_calls(
            [mock.call()(daemon_manager._monitor.exit)],
            [mock.call()(daemon_manager.stop)]
        )

        # hyperdrive not running
        process.poll.return_value = True
        daemon_manager._monitor.add_child_processes.called = False

        with mock.patch.object(daemon_manager, 'addresses', side_effect=none), \
             mock.patch('subprocess.Popen', return_value=process), \
             mock.patch('os.makedirs') as makedirs:

            with self.assertRaises(RuntimeError):
                daemon_manager.start()

            register.assert_called_with(daemon_manager.stop)

            assert register.call_count == 2
            assert daemon_manager._monitor.start.called
            assert makedirs.called
            assert not daemon_manager._monitor.add_child_processes.called

        process.poll.return_value = None
        daemon_manager._monitor.add_child_processes.called = False

        with mock.patch.object(daemon_manager, 'addresses', side_effect=none), \
             mock.patch('subprocess.Popen', return_value=process), \
             mock.patch('os.makedirs') as makedirs:

            daemon_manager.start()

            register.assert_called_with(daemon_manager.stop)
            assert register.call_count == 2
            assert daemon_manager._monitor.start.called
            assert makedirs.called
            daemon_manager._monitor.add_child_processes.assert_called_with(process)

        # hyperdrive is running
        process.poll.return_value = True
        daemon_manager._monitor.add_child_processes.called = False

        with mock.patch.object(daemon_manager, 'addresses', side_effect=ports), \
             mock.patch('subprocess.Popen', return_value=process), \
             mock.patch('os.makedirs') as makedirs:

            daemon_manager.start()

            register.assert_called_with(daemon_manager.stop)
            assert register.call_count == 2
            assert daemon_manager._monitor.start.called
            assert not makedirs.called
            assert not daemon_manager._monitor.add_child_processes.called

    def test_daemon_running(self):

        daemon_manager = HyperdriveDaemonManager(self.path)

        def raise_exc():
            raise ConnectionError()

        with mock.patch('golem.network.hyperdrive.client.HyperdriveClient.addresses',
                   side_effect=raise_exc):
            assert not daemon_manager.addresses()

        with mock.patch('golem.network.hyperdrive.client.HyperdriveClient.addresses',
                   side_effect=lambda *_: {'TCP': {'port': 1234}}):
            assert daemon_manager.addresses()

