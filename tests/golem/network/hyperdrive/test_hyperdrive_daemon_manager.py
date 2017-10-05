from mock import patch, Mock, call
from requests import ConnectionError

from golem.network.hyperdrive.daemon_manager import HyperdriveDaemonManager
from golem.testutils import TempDirFixture


@patch('golem.network.hyperdrive.daemon_manager.ProcessMonitor')
@patch('atexit.register')
class TestHyperdriveDaemonManager(TempDirFixture):

    def test_start(self, register, *_):
        def addresses(*_):
            return dict(
                uTP=('0.0.0.0', 3282),
                TCP=('0.0.0.0', 3282)
            )

        process = Mock()

        # initialization
        dm = HyperdriveDaemonManager(self.path)
        monitor = dm._monitor

        monitor.add_callbacks.assert_called_with(dm._start)
        register.assert_called_with(dm.stop)

        # hyperdrive is running, no address response
        process.poll.return_value = True
        monitor.add_child_processes.called = False

        with patch.object(dm, 'addresses', return_value=None), \
             patch('subprocess.Popen', return_value=process), \
             patch('os.makedirs') as makedirs:

            with self.assertRaises(RuntimeError):
                dm.start()

            assert monitor.start.called
            assert not monitor.add_child_processes.called
            assert makedirs.called

        # hyperdrive is running, valid address response
        process.poll.return_value = True
        monitor.add_child_processes.called = False

        with patch.object(dm, 'addresses', return_value=addresses), \
             patch('subprocess.Popen', return_value=process), \
             patch('os.makedirs') as makedirs:

            dm.start()

            assert monitor.start.called
            assert not monitor.add_child_processes.called
            assert not makedirs.called

        # hyperdrive not running
        process.poll.return_value = None
        monitor.add_child_processes.called = False

        with patch.object(dm, 'addresses', return_value=None), \
            patch('subprocess.Popen', return_value=process), \
            patch('os.makedirs') as makedirs:

            dm.start()

            assert monitor.start.called
            monitor.add_child_processes.assert_called_with(process)
            assert makedirs.called

    def test_addresses_and_ports(self, *_):
        to_patch = 'golem.network.hyperdrive.client.HyperdriveClient.addresses'

        public_ip = '1.2.3.4'

        addresses = {
            'TCP': ('0.0.0.0', 3282),
            'uTP': ('0.0.0.0', 3283)
        }
        expected_public = {
            'TCP': (public_ip, 3282),
            'uTP': (public_ip, 3283)
        }

        def raise_exc():
            raise ConnectionError()

        dm = HyperdriveDaemonManager(self.path)

        with patch(to_patch, side_effect=raise_exc):
            assert not dm.addresses()

        with patch(to_patch, return_value=addresses):
            assert dm.addresses() == addresses

            assert dm.public_addresses(public_ip) == expected_public
            assert dm.public_addresses(public_ip, addresses) == expected_public
            assert dm.public_addresses(public_ip, dict()) == dict()

            assert dm.ports() == {3282, 3283}
            assert dm.ports(addresses) == {3282, 3283}
            assert dm.ports(dict()) == set()

