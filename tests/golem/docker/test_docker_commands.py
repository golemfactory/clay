from subprocess import CalledProcessError
from unittest import mock, TestCase

from golem.docker.commands.docker_for_mac import DockerForMacCommandHandler


@mock.patch('subprocess.Popen')
@mock.patch('subprocess.check_call')
class TestDockerForMacCommandHandler(TestCase):

    PKG_PATH = 'golem.docker.commands.docker_for_mac.DockerForMacCommandHandler'

    @mock.patch('sys.exit')
    def test_start_success(self, _sys_exit, check_call, _):
        check_call.return_value = 0

        with mock.patch(f'{self.PKG_PATH}.wait_until_started') as wait:
            DockerForMacCommandHandler.start()
            assert wait.called

    @mock.patch('sys.exit')
    def test_start_failure(self, sys_exit, check_call, _):
        check_call.side_effect = CalledProcessError(1, [])

        with mock.patch(f'{self.PKG_PATH}.wait_until_started') as wait:
            DockerForMacCommandHandler.start()
            assert not wait.called
            assert sys_exit.called

    def test_stop_success(self, check_call, _):
        check_call.return_value = 0

        with mock.patch.object(DockerForMacCommandHandler,
                               'wait_until_stopped') as wait:
            with mock.patch.object(DockerForMacCommandHandler,
                                   'pid', return_value=1234):

                DockerForMacCommandHandler.stop()
                assert wait.called

    def test_stop_failure(self, check_call, _):
        check_call.side_effect = CalledProcessError(1, [])

        with mock.patch(f'{self.PKG_PATH}.wait_until_stopped') as wait:
            with mock.patch.object(DockerForMacCommandHandler,
                                   'pid', return_value=1234):

                DockerForMacCommandHandler.stop()
                assert not wait.called

    def test_status(self, *_):

        with mock.patch(f'{self.PKG_PATH}.pid', return_value=1234):
            assert DockerForMacCommandHandler.status() == 'Running'

        with mock.patch(f'{self.PKG_PATH}.pid', return_value=None):
            assert DockerForMacCommandHandler.status() == ''

    def test_pid(self, _, popen):

        stdout, stderr = mock.Mock(), mock.Mock()
        popen.return_value = mock.Mock(communicate=mock.Mock(
            return_value=(stdout, stderr)
        ))

        stdout.strip.return_value = b'user 1234'
        assert DockerForMacCommandHandler.pid() == 1234

        stdout.strip.return_value = b''
        assert DockerForMacCommandHandler.pid() is None
