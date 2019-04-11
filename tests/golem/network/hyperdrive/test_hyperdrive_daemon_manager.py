from unittest.mock import patch, Mock

import requests
import semantic_version

from golem.network.hyperdrive.daemon_manager import HyperdriveDaemonManager
from golem.testutils import TempDirFixture

from tests.factories.hyperdrive import hyperdrive_client_kwargs


class TestHyperdriveDaemonManager(TempDirFixture):

    @patch('golem.network.hyperdrive.daemon_manager.ProcessMonitor')
    def setUp(self, *_):
        super().setUp()

        self.dm = HyperdriveDaemonManager(
            self.path, client_config=hyperdrive_client_kwargs(wrapped=False))
        self.monitor = self.dm._monitor

    @patch('golem.network.hyperdrive.daemon_manager.'
           'HyperdriveDaemonManager._check_version')
    @patch('golem.network.hyperdrive.daemon_manager.'
           'HyperdriveDaemonManager._wait')
    def test_start_not_running(self, *_):
        dm, monitor = self.dm, self.monitor
        process = Mock()

        process.poll.return_value = None
        monitor.add_child_processes.called = False

        with patch.object(dm, 'addresses', return_value=None), \
            patch('subprocess.Popen', return_value=process), \
            patch('os.makedirs') as makedirs:

            dm.start()

            assert monitor.start.called
            monitor.add_child_processes.assert_called_with(process)
            assert makedirs.called

    @patch('golem.network.hyperdrive.daemon_manager.'
           'HyperdriveDaemonManager._check_version')
    def test_start_running(self, *_):
        dm, monitor = self.dm, self.monitor
        process = Mock()

        addresses = dict(
            uTP=('0.0.0.0', 3282),
            TCP=('0.0.0.0', 3282)
        )

        process.poll.return_value = True
        monitor.add_child_processes.called = False

        with patch.object(dm, 'addresses', return_value=addresses), \
            patch('subprocess.Popen', return_value=process), \
            patch('os.makedirs') as makedirs:

            dm.start()
            assert monitor.start.called
            assert not monitor.add_child_processes.called
            assert not makedirs.called

    @patch('golem.network.hyperdrive.daemon_manager.'
           'HyperdriveDaemonManager._check_version')
    def test_start_invalid_response(self, *_):
        dm, monitor = self.dm, self.monitor
        process = Mock()

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

    @patch('golem.network.hyperdrive.client.HyperdriveClient.addresses')
    def test_addresses_and_ports(self, client_addresses, *_):
        dm = self.dm
        public_ip = '1.2.3.4'

        addresses = {
            'TCP': ('0.0.0.0', 3282),
            'uTP': ('0.0.0.0', 3283)
        }
        expected_public = {
            'TCP': (public_ip, 3282),
            'uTP': (public_ip, 3283)
        }

        client_addresses.return_value = addresses
        assert dm.addresses() == addresses

        assert dm.public_addresses(public_ip) == expected_public
        assert dm.public_addresses(public_ip, addresses) == expected_public
        assert dm.public_addresses(public_ip, dict()) == dict()

        assert dm.ports() == {3282, 3283}
        assert dm.ports(addresses) == {3282, 3283}
        assert dm.ports(dict()) == set()

    @patch('golem.network.hyperdrive.client.HyperdriveClient.addresses')
    def test_addresses_error(self, client_addresses, *_):
        dm = self.dm
        client_addresses.side_effect = requests.ConnectionError
        assert not dm.addresses()

    def test_wait(self, *_):
        dm = self.dm
        dm.addresses = Mock()
        dm._critical_error = Mock()

        dm.addresses.return_value = {'TCP': ('0.0.0.0', 3282)}
        dm._wait(timeout=1)
        assert not dm._critical_error.called

        dm.addresses.return_value = None
        dm._wait(timeout=1)
        assert dm._critical_error.called

    def test_version_error(self):
        err = requests.ConnectionError

        with patch('subprocess.check_output', side_effect=OSError):
            with patch.object(self.dm._client, 'id', side_effect=err):
                with self.assertRaises(SystemExit):
                    assert self.dm.version() is None

    def test_version_from_process(self):
        err = requests.ConnectionError
        response = dict(id='id')

        with patch('subprocess.check_output', return_value=b'0.2.5'):
            with patch.object(self.dm._client, 'id', side_effect=err):

                assert self.dm.version() == semantic_version.Version('0.2.5')

        with patch('subprocess.check_output', return_value=b'0.2.5'):
            with patch.object(self.dm._client, 'id', return_value=response):

                assert self.dm.version() == semantic_version.Version('0.2.5')

    def test_version_from_api(self):
        response = dict(id='id', version='0.2.4')

        with patch('subprocess.check_output', return_value=b'0.2.5'):
            with patch.object(self.dm._client, 'id', return_value=response):

                assert self.dm.version() == semantic_version.Version('0.2.4')

    def test_check_version_error(self):

        low_version = semantic_version.Version('0.0.1')

        with patch.object(self.dm, 'version', return_value=low_version):
            with self.assertRaises(RuntimeError):
                self.dm._check_version()

    def test_check_version(self):

        same_version = self.dm._min_version
        high_version = semantic_version.Version('10.0.1')

        with patch.object(self.dm, 'version', return_value=same_version):
            self.dm._check_version()

        with patch.object(self.dm, 'version', return_value=high_version):
            self.dm._check_version()
