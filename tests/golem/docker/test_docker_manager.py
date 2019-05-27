# pylint: disable=too-many-lines
import functools
import sys
from collections import namedtuple
from subprocess import CalledProcessError
from unittest import TestCase, mock

from golem.docker.config import DEFAULTS
from tests.golem.docker.test_hypervisor import command, MockHypervisor, \
    MockDockerManager, raise_exception, raise_process_exception

ConfigMock = namedtuple('ConfigMock', ('num_cores', 'max_memory_size'))


class TestDockerManager(TestCase):  # pylint: disable=too-many-public-methods

    def test_build_config_odd_memory_size(self):
        manager = MockDockerManager()
        manager.hypervisor = MockHypervisor(manager)
        config = ConfigMock(None, 1025 * 1024)
        manager.build_config(config)
        self.assertEqual(manager.get_config()['memory_size'], 1024)

    def test_build_config_ok(self):
        manager = MockDockerManager()
        cpu_to_check = 4
        mem_to_check = 4096
        config = ConfigMock(cpu_to_check, mem_to_check * 1024)
        manager.build_config(config)
        self.assertEqual(
            manager.get_config(),
            {'cpu_count': cpu_to_check, 'memory_size': mem_to_check})

    def test_update_config(self):
        status_switch = [True]

        def status_cb():
            if status_switch[0]:
                status_switch[0] = False
                return True
            else:
                return status_switch[0]

        def done_cb(_):
            pass

        config = ConfigMock(0, 768)

        dmm = MockDockerManager()
        dmm.pull_images = mock.Mock()
        dmm.build_images = mock.Mock()

        hypervisor = mock.Mock()
        hypervisor.constraints.return_value = DEFAULTS
        hypervisor.reconfig_ctx.return_value = mock.Mock(
            __enter__=mock.Mock(),
            __exit__=mock.Mock(),
        )

        dmm._select_hypervisor = mock.Mock(return_value=hypervisor)

        with mock.patch.object(dmm, 'command'):
            dmm.build_config(config)
            dmm.check_environment()

        dmm.update_config(
            status_cb, done_cb, in_background=False, work_dir=None)
        dmm.update_config(
            status_cb, done_cb, in_background=True, work_dir=None)

    def test_constrain_not_called(self):
        dmm = MockDockerManager()
        dmm._diff_constraints = mock.Mock(return_value=dict())

        dmm.hypervisor = MockHypervisor(dmm)

        dmm.constrain()
        assert not dmm.hypervisor.constrain.called

    def test_constrain_called(self):
        diff = dict(cpu_count=0)
        dmm = MockDockerManager()
        dmm._diff_constraints = mock.Mock(return_value=diff)

        dmm.hypervisor = MockHypervisor(dmm)
        dmm.hypervisor._set_env = mock.Mock()

        dmm.constrain()
        assert dmm.hypervisor.constrain.called

        _, kwargs = dmm.hypervisor.constrain.call_args_list.pop()

        assert len(kwargs) == len(diff)
        assert kwargs['cpu_count'] == DEFAULTS['cpu_count']
        assert kwargs['memory_size'] == DEFAULTS['memory_size']

    def test_diff_constraints(self):
        dmm = MockDockerManager()
        diff = dmm._diff_constraints

        assert diff(DEFAULTS, dict()) == dict()
        assert diff(dict(), DEFAULTS) == DEFAULTS

        old = DEFAULTS
        new = dict(cpu_count=DEFAULTS['cpu_count'])
        expected = dict()
        assert diff(old, new) == expected

        old = DEFAULTS
        new = dict(
            cpu_count=DEFAULTS['cpu_count'] + 1, unknown_key='value'
        )
        expected = dict(cpu_count=DEFAULTS['cpu_count'] + 1)
        assert diff(old, new) == expected

    def test_command(self):
        dmm = MockDockerManager()

        with mock.patch.dict(
            'golem.docker.commands.docker.DockerCommandHandler.commands',
            dict(test=[sys.executable, '--version'])
        ):
            assert dmm.command('test').startswith('Python')
            assert not dmm.command('deadbeef')

    @mock.patch('golem.docker.manager.DockerForMac.is_available',
                return_value=False)
    @mock.patch('golem.docker.manager.HyperVHypervisor.is_available',
                return_value=True)
    @mock.patch('golem.docker.manager.HyperVHypervisor.instance')
    @mock.patch('golem.docker.manager.XhyveHypervisor.instance')
    def test_get_hypervisor(self, xhyve_instance, hyperv_instance, *_):

        def reset():
            xhyve_instance.called = False
            hyperv_instance.called = False

        dmm = MockDockerManager()

        with mock.patch('golem.docker.manager.is_windows',
                        return_value=True):

            assert dmm._select_hypervisor()
            assert hyperv_instance.called
            assert not xhyve_instance.called

        reset()

        with mock.patch('golem.docker.manager.is_windows',
                        return_value=False):
            with mock.patch('golem.docker.manager.is_osx',
                            return_value=True):

                assert dmm._select_hypervisor()
                assert not hyperv_instance.called
                assert xhyve_instance.called

        reset()

        with mock.patch('golem.docker.manager.is_windows',
                        return_value=False):
            with mock.patch('golem.docker.manager.is_osx',
                            return_value=False):

                assert not dmm._select_hypervisor()
                assert not hyperv_instance.called
                assert not xhyve_instance.called

    @mock.patch('golem.docker.manager.is_windows', return_value=True)
    @mock.patch('golem.docker.manager.is_linux', return_value=False)
    @mock.patch('golem.docker.manager.is_osx', return_value=False)
    @mock.patch('golem.docker.manager.HyperVHypervisor.is_available',
                return_value=True)
    def test_check_environment_windows_hyperv(self, *_):
        dmm = MockDockerManager()
        dmm.pull_images = mock.Mock()
        dmm.build_images = mock.Mock()

        with mock.patch('golem.docker.manager.HyperVHypervisor.instance',
                        mock.Mock(vm_running=mock.Mock(return_value=False))):
            # pylint: disable=no-member

            with mock.patch.object(dmm, 'command'):
                dmm.check_environment()

                assert dmm.hypervisor
                assert dmm.hypervisor.setup.called
                assert dmm.pull_images.called
                assert not dmm.build_images.called

    @mock.patch('golem.docker.manager.is_windows', return_value=True)
    @mock.patch('golem.docker.manager.is_linux', return_value=False)
    @mock.patch('golem.docker.manager.is_osx', return_value=False)
    @mock.patch('golem.docker.manager.HyperVHypervisor.is_available',
                return_value=False)
    def test_check_environment_windows_no_hyperv(self, *_):
        dmm = MockDockerManager()
        dmm.pull_images = mock.Mock()
        dmm.build_images = mock.Mock()

        with mock.patch('golem.docker.manager.VirtualBoxHypervisor.instance',
                        mock.Mock(vm_running=mock.Mock(return_value=False))):
            # pylint: disable=no-member

            with mock.patch.object(dmm, 'command'):
                dmm.check_environment()

                assert dmm.hypervisor
                assert dmm.hypervisor.setup.called
                assert dmm.pull_images.called
                assert not dmm.build_images.called

    @mock.patch('golem.docker.manager.is_windows', return_value=False)
    @mock.patch('golem.docker.manager.is_linux', return_value=True)
    @mock.patch('golem.docker.manager.is_osx', return_value=False)
    def test_check_environment_linux(self, *_):
        dmm = MockDockerManager()
        dmm.pull_images = mock.Mock()
        dmm.build_images = mock.Mock()

        with mock.patch.object(dmm, 'command'):
            assert not dmm.check_environment()
            assert dmm.pull_images.called
            assert not dmm.build_images.called
            assert not dmm.hypervisor
            assert dmm._env_checked

    @mock.patch('golem.docker.manager.DockerForMac.is_available',
                return_value=False)
    @mock.patch('golem.docker.manager.is_windows', return_value=False)
    @mock.patch('golem.docker.manager.is_linux', return_value=False)
    @mock.patch('golem.docker.manager.is_osx', return_value=True)
    def test_check_environment_osx(self, *_):
        dmm = MockDockerManager()
        hypervisor = mock.Mock(
            start_vm=mock.Mock(),
            stop_vm=mock.Mock(),
            vm_running=mock.Mock(return_value=False),
        )

        dmm.pull_images = mock.Mock()
        dmm.build_images = mock.Mock()

        with mock.patch('golem.docker.manager.XhyveHypervisor.instance',
                        hypervisor):
            # pylint: disable=no-member

            with mock.patch.object(dmm, 'command'):
                dmm.check_environment()

                assert not dmm.hypervisor.create.called
                assert dmm.pull_images.called
                assert not dmm.build_images.called
                assert not dmm.hypervisor.start_vm.called
                assert not dmm.hypervisor._set_env.called

    @mock.patch('golem.docker.manager.is_windows', return_value=False)
    @mock.patch('golem.docker.manager.is_linux', return_value=False)
    @mock.patch('golem.docker.manager.is_osx', return_value=False)
    def test_check_environment_none(self, *_):
        dmm = MockDockerManager()
        dmm.pull_images = mock.Mock()
        dmm.build_images = mock.Mock()

        with self.assertRaises(EnvironmentError):
            dmm.check_environment()

        assert not dmm.hypervisor
        assert not dmm.pull_images.called
        assert not dmm.build_images.called
        assert dmm._env_checked

    @mock.patch('golem.docker.manager.is_windows', return_value=False)
    @mock.patch('golem.docker.manager.is_linux', return_value=False)
    @mock.patch('golem.docker.manager.is_osx', return_value=False)
    def test_check_environment_unsupported(self, *_):
        dmm = MockDockerManager()
        dmm.command = lambda *a, **kw: raise_exception('Docker not available')
        dmm.pull_images = mock.Mock()
        dmm.build_images = mock.Mock()

        with self.assertRaises(EnvironmentError):
            dmm.check_environment()

        assert not dmm.pull_images.called
        assert not dmm.build_images.called
        assert dmm._env_checked

    def test_pull_images(self):
        pulls = [0]

        def command(key, *args, **kwargs):
            if key == 'images':
                return ''
            elif key == 'pull':
                pulls[0] += 1
                return True

        with mock.patch.object(MockDockerManager, 'command',
                               side_effect=command):
            dmm = MockDockerManager()
            dmm.pull_images()

        from apps.core import nvgpu
        if nvgpu.is_supported():
            expected = 8
        else:
            expected = 6

        assert pulls[0] == expected

    @mock.patch('os.chdir')
    def test_build_images(self, os_chdir):

        builds = [0]
        tags = [0]

        def command(key, *args, **kwargs):
            if key == 'images':
                return ''
            elif key == 'build':
                builds[0] += 1
                return True
            elif key == 'tag':
                tags[0] += 1
                return True

        with mock.patch.object(MockDockerManager, 'command',
                               side_effect=command):
            dmm = MockDockerManager()
            dmm.build_images()

        from apps.core import nvgpu
        if nvgpu.is_supported():
            expected = 8
        else:
            expected = 6

        assert builds[0] == expected
        assert tags[0] == expected
        assert len(os_chdir.mock_calls) == 2 * expected

    def test_recover_vm_connectivity(self):
        callback = mock.Mock()

        dmm = MockDockerManager()
        dmm._save_and_resume = mock.Mock()
        dmm.check_environment = mock.Mock()

        def reset():
            callback.called = False
            dmm.check_environment.called = False
            dmm._save_and_resume.called = False

        dmm._env_checked = True

        dmm.recover_vm_connectivity(callback, in_background=False)
        assert not dmm._save_and_resume.called

        reset()

        dmm._env_checked = False

        dmm.recover_vm_connectivity(callback, in_background=False)
        assert not dmm._save_and_resume.called

        reset()

        dmm._env_checked = True
        dmm.hypervisor = MockHypervisor(dmm)

        dmm.recover_vm_connectivity(callback, in_background=False)
        assert dmm._save_and_resume.called

        reset()
        dmm.recover_vm_connectivity(callback, in_background=True)

    def test_save_and_resume(self):
        dmm = MockDockerManager()
        dmm.hypervisor = MockHypervisor(dmm)
        dmm.hypervisor.command = mock.Mock()
        dmm.hypervisor._set_env_from_output = mock.Mock()
        dmm.hypervisor._set_env()

        callback = mock.Mock()
        dmm._save_and_resume(callback)
        assert callback.called

    def test_set_env(self):
        hypervisor = MockHypervisor(mock.Mock())
        environ = dict()

        def raise_on_env(key, *_a, **_kw):
            if key == 'env':
                raise_process_exception('error')
            return key

        with mock.patch.dict('os.environ', environ):

            with mock.patch.object(
                hypervisor, 'command',
                side_effect=functools.partial(command, hypervisor)
            ):
                hypervisor._set_env()
                assert hypervisor._config_dir == 'tmp'

            with mock.patch.object(
                hypervisor, 'command',
                side_effect=raise_on_env
            ):
                with self.assertRaises(CalledProcessError):
                    hypervisor._set_env()

            with mock.patch.object(
                hypervisor, 'command',
                side_effect=raise_process_exception
            ):
                with self.assertRaises(CalledProcessError):
                    hypervisor._set_env()
