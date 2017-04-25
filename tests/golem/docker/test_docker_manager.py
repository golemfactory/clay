import json
import os
import unittest
from contextlib import contextmanager
from subprocess import CalledProcessError

import mock
from golem.docker.manager import DockerManager, FALLBACK_DOCKER_MACHINE_NAME, VirtualBoxHypervisor, XhyveHypervisor, \
    Hypervisor, logger
from golem.testutils import TempDirFixture
from golem.tools.assertlogs import LogTestCase

MACHINE_NAME = FALLBACK_DOCKER_MACHINE_NAME


class MockConfig(object):
    def __init__(self, num_cores, max_memory_size, max_resource_size):
        self.num_cores = num_cores
        self.max_memory_size = max_memory_size
        self.max_resource_size = max_resource_size

    def to_dict(self):
        return dict(
            num_cores=self.num_cores,
            max_memory_size=self.max_memory_size,
            max_resource_size=self.max_resource_size,
        )


class MockVirtualBox(mock.MagicMock):
    def __init__(self, *args, **kw):
        super(MockVirtualBox, self).__init__(*args, **kw)
        self.version = "1.0"

    @staticmethod
    def find_machine(name):
        if name == MACHINE_NAME:
            return MockMachine(name=MACHINE_NAME)
        return None


class MockConsole(mock.MagicMock):
    def __init__(self, *args, **kw):
        super(MockConsole, self).__init__(*args, **kw)


class MockSession(mock.MagicMock):
    def __init__(self, *args, **kw):
        super(MockSession, self).__init__(*args, **kw)
        self.console = MockConsole()
        self.machine = kw.pop('machine', None)


class MockLockType(mock.MagicMock):

    states = {
        0: 'Null',
        1: 'Shared',
        2: 'Write',
        3: 'VM'
    }

    null = 0
    shared = 1
    write = 2
    vm = 3

    def __init__(self, value):
        super(MockLockType, self).__init__()
        self.value = value

    def __str__(self):
        return self.states.get(self.value, self.states[0])


class MockMachine(mock.MagicMock):
    def __init__(self, *args, **kw):
        super(MockMachine, self).__init__(*args, **kw)
        self.state = MockState()
        self.name = kw.pop('name', None)
        self.session = MockSession(machine=self)


class MockState(mock.MagicMock):
    states = {
        0: 'Null',
        1: 'Disabled',
        2: 'SaveState',
        3: 'PowerOff',
        4: 'AcpiShutdown'
    }

    def __str__(self):
        return self.states.get(self.value, self.states[0])


class MockThreadExecutor(mock.Mock):
    pass


class MockHypervisor(mock.Mock):

    def __init__(self):
        super(MockHypervisor, self).__init__()
        self.recover_ctx = self.ctx
        self.restart_ctx = self.ctx
        self.constrain = mock.Mock()

    @contextmanager
    def ctx(self, name, *_):
        yield name

    def constraints(*_):
        return dict()


class MockDockerManager(DockerManager):

    def __init__(self,
                 use_parent_methods=False,
                 config_desc=None,
                 config_dir=None):

        super(MockDockerManager, self).__init__(config_desc)

        self.command_calls = []

        self._threads = MockThreadExecutor()
        self.set_defaults(config_dir)
        self.use_parent_methods = use_parent_methods

    def set_defaults(self, config_dir=None):
        self._config = dict(self.defaults)
        self._config_dir = config_dir
        self.docker_machine = MACHINE_NAME

    def command(self, key, machine_name=None, args=None, check_output=True, shell=False):
        self.command_calls.append([key, machine_name, args, check_output, shell])

        if self.use_parent_methods:
            return super(MockDockerManager, self).command(key,
                                                          machine_name=machine_name,
                                                          args=args,
                                                          check_output=check_output,
                                                          shell=shell)
        elif key == 'env':
            return '\n'.join([
                'SET GOLEM_TEST=1',
                '',
                'INVALID DOCKER=2',
                'SET DOCKER_CERT_PATH="{}"'.format(os.path.join('tmp', 'golem'))
            ])
        elif key == 'list':
            return MACHINE_NAME
        elif key == 'status':
            return 'Running'
        elif key == 'version':
            return '1.0.0'
        elif key == 'help':
            return '[help contents]'
        elif key == 'regenerate_certs':
            return 'certs'
        elif key not in self.docker_machine_commands:
            raise KeyError(key)

        return MACHINE_NAME

    @staticmethod
    def _set_env_variable(name, value):
        pass


def raise_exception(msg, *args, **kwargs):
    raise TypeError(msg)


class Erroneous(mock.Mock):
    @property
    def cpu_count(self):
        raise_exception("Read")

    @cpu_count.setter
    def cpu_count(self, value):
        raise_exception("Write")


class TestDockerManager(unittest.TestCase):

    def test_start(self):
        dmm = MockDockerManager()
        dmm.start_docker_machine(MACHINE_NAME)
        assert ['start', MACHINE_NAME, None, False, False] in dmm.command_calls

    def test_stop(self):
        dmm = MockDockerManager()
        dmm.stop_docker_machine(MACHINE_NAME)
        assert ['stop', MACHINE_NAME, None, False, False] in dmm.command_calls

    def test_running(self):
        dmm = MockDockerManager()
        dmm.docker_machine = None

        with self.assertRaises(EnvironmentError):
            dmm.docker_machine_running()

        dmm.docker_machine = MACHINE_NAME
        assert dmm.docker_machine_running()

    def test_build_config(self):
        dmm = MockDockerManager()
        assert dmm._config == dmm.defaults

        dmm.build_config(None)
        assert all([val == dmm.defaults[key] for key, val in dmm._config.iteritems()])

        config = MockConfig(0, 768, 512)

        dmm.build_config(config)
        assert len(dmm._config) < len(config.to_dict())
        assert dmm._config != dmm.defaults
        assert dmm._config.get('cpu_count') == dmm.min_constraints.get('cpu_count')
        assert dmm._config.get('memory_size') == dmm.min_constraints.get('memory_size')

        config = MockConfig(10, 10000000, 20000)

        dmm.build_config(config)
        assert dmm._config.get('cpu_count') == 10
        assert dmm._config.get('memory_size') >= 10000

    def test_update_config(self):
        status_switch = [True]

        def status_cb():
            if status_switch[0]:
                status_switch[0] = False
                return True
            else:
                return status_switch[0]

        def done_cb():
            pass

        config = MockConfig(0, 768, 512)

        dmm = MockDockerManager()
        dmm.pull_images = mock.Mock()
        dmm.build_images = mock.Mock()
        dmm.hypervisor = mock.Mock()
        dmm.hypervisor.constraints.return_value = dmm.defaults

        dmm.build_config(config)
        dmm.check_environment()
        dmm.set_defaults()

        dmm.update_config(status_cb, done_cb, in_background=False)
        dmm.update_config(status_cb, done_cb, in_background=True)

    def test_constrain(self):
        dmm = MockDockerManager()
        dmm.hypervisor = MockHypervisor()
        dmm._diff_constraints = mock.Mock()
        dmm._set_docker_machine_env = mock.Mock()

        def reset():
            dmm.hypervisor.constrain.called = False

        dmm._diff_constraints.return_value = dict()
        dmm.constrain(MACHINE_NAME)
        assert not dmm.hypervisor.constrain.called

        reset()

        diff = dict(cpu_count=0)
        dmm._diff_constraints.return_value = dict(diff)
        dmm.constrain(MACHINE_NAME)

        args, kwargs = dmm.hypervisor.constrain.call_args_list.pop()
        assert dmm._set_docker_machine_env.called

        assert args[0] == MACHINE_NAME
        assert len(kwargs) > len(diff)
        assert kwargs['cpu_count'] == dmm.defaults['cpu_count']
        assert kwargs['memory_size'] == dmm.defaults['memory_size']

    def test_diff_constraints(self):
        dmm = MockDockerManager()
        diff = dmm._diff_constraints

        assert diff(dmm.defaults, dmm.defaults) == dict()
        assert diff(dmm.defaults, dict()) == dict()
        assert diff(dict(), dmm.defaults) == dmm.defaults

        old = dmm.defaults
        new = dict(cpu_count=dmm.defaults['cpu_count'])
        expected = dict()
        assert diff(old, new) == expected

        old = dmm.defaults
        new = dict(cpu_count=dmm.defaults['cpu_count'] + 1, unknown_key='value')
        expected = dict(cpu_count=dmm.defaults['cpu_count'] + 1)
        assert diff(old, new) == expected

    def test_command(self):
        dmm = MockDockerManager(use_parent_methods=True)
        dmm.docker_machine_commands['test'] = ['python', '--version']

        assert dmm.command('test', check_output=True) == ""
        assert dmm.command('test', check_output=False) == 0
        assert not dmm.command('deadbeef')

    @mock.patch('golem.docker.manager.VirtualBoxHypervisor.instance')
    @mock.patch('golem.docker.manager.XhyveHypervisor.instance')
    def test_get_hypervisor(self, xhyve_instance, virtualbox_instance):

        def reset():
            xhyve_instance.called = False
            virtualbox_instance.called = False

        dmm = MockDockerManager()

        with mock.patch('golem.docker.manager.is_windows',
                        return_value=True):

            assert dmm._get_hypervisor()
            assert virtualbox_instance.called
            assert not xhyve_instance.called

        reset()

        with mock.patch('golem.docker.manager.is_windows',
                        return_value=False):
            with mock.patch('golem.docker.manager.is_osx',
                            return_value=True):

                assert dmm._get_hypervisor()
                assert not virtualbox_instance.called
                assert xhyve_instance.called

        reset()

        with mock.patch('golem.docker.manager.is_windows',
                        return_value=False):
            with mock.patch('golem.docker.manager.is_osx',
                            return_value=False):

                assert not dmm._get_hypervisor()
                assert not virtualbox_instance.called
                assert not xhyve_instance.called

    @mock.patch('golem.docker.manager.is_windows', return_value=True)
    @mock.patch('golem.docker.manager.is_linux', return_value=False)
    @mock.patch('golem.docker.manager.is_osx', return_value=False)
    def test_check_environment_windows(self, *_):
        dmm = MockDockerManager()

        dmm.start_docker_machine = mock.Mock()
        dmm.stop_docker_machine = mock.Mock()
        dmm.docker_machine_running = lambda *_: False
        dmm._set_docker_machine_env = mock.Mock()
        dmm.pull_images = mock.Mock()
        dmm.build_images = mock.Mock()

        with mock.patch('golem.docker.manager.VirtualBoxHypervisor.instance'):
            dmm.check_environment()

            assert dmm.docker_machine == MACHINE_NAME
            assert not dmm.hypervisor.create.called
            assert dmm.start_docker_machine.called
            assert dmm._set_docker_machine_env.called
            assert dmm.pull_images.called
            assert not dmm.build_images.called

    @mock.patch('golem.docker.manager.is_windows', return_value=False)
    @mock.patch('golem.docker.manager.is_linux', return_value=True)
    @mock.patch('golem.docker.manager.is_osx', return_value=False)
    def test_check_environment_linux(self, *_):
        dmm = MockDockerManager()
        dmm.pull_images = mock.Mock()
        dmm.build_images = mock.Mock()
        assert not dmm.check_environment()
        assert dmm.pull_images.called
        assert not dmm.build_images.called
        assert not dmm.docker_machine
        assert dmm._env_checked

    @mock.patch('golem.docker.manager.is_windows', return_value=False)
    @mock.patch('golem.docker.manager.is_linux', return_value=False)
    @mock.patch('golem.docker.manager.is_osx', return_value=True)
    def test_check_environment_osx(self, *_):
        dmm = MockDockerManager()

        dmm.start_docker_machine = mock.Mock()
        dmm.stop_docker_machine = mock.Mock()
        dmm.docker_machine_running = lambda *_: False
        dmm._set_docker_machine_env = mock.Mock()
        dmm.pull_images = mock.Mock()
        dmm.build_images = mock.Mock()

        with mock.patch('golem.docker.manager.XhyveHypervisor.instance'):
            dmm.check_environment()

            assert dmm.docker_machine == MACHINE_NAME
            assert not dmm.hypervisor.create.called
            assert dmm.pull_images.called
            assert not dmm.build_images.called
            assert dmm.start_docker_machine.called
            assert dmm._set_docker_machine_env.called

    @mock.patch('golem.docker.manager.is_windows', return_value=False)
    @mock.patch('golem.docker.manager.is_linux', return_value=False)
    @mock.patch('golem.docker.manager.is_osx', return_value=False)
    def test_check_environment_none(self, *_):
        dmm = MockDockerManager()
        dmm.pull_images = mock.Mock()
        dmm.build_images = mock.Mock()
        assert not dmm.check_environment()
        assert not dmm.docker_machine
        assert dmm.pull_images.called
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
        assert not dmm._env_checked

    def test_pull_images(self):
        pulls = [0]

        def command(key, *args, **kwargs):
            if key == 'images':
                return ''
            elif key == 'pull':
                pulls[0] += 1
                return True

        with mock.patch.object(MockDockerManager, 'command', side_effect=command):
            dmm = MockDockerManager()
            dmm.pull_images()

        assert pulls[0] == 3

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

        with mock.patch.object(MockDockerManager, 'command', side_effect=command):
            dmm = MockDockerManager()
            dmm.build_images()

        assert builds[0] == 3
        assert tags[0] == 3
        assert len(os_chdir.mock_calls) == 6

    def test_recover_vm_connectivity(self):
        callback = mock.Mock()

        dmm = MockDockerManager()
        dmm._save_and_resume = mock.Mock()
        dmm.check_environment = mock.Mock()
        dmm.hypervisor = MockHypervisor()

        def reset():
            callback.called = False
            dmm.check_environment.called = False
            dmm._save_and_resume.called = False

        dmm._env_checked = True
        dmm.docker_machine = None

        dmm.recover_vm_connectivity(callback, in_background=False)
        assert not dmm._save_and_resume.called

        reset()

        dmm._env_checked = False
        dmm.docker_machine = None

        dmm.recover_vm_connectivity(callback, in_background=False)
        assert not dmm._save_and_resume.called

        reset()

        dmm._env_checked = True
        dmm.docker_machine = MACHINE_NAME

        dmm.recover_vm_connectivity(callback, in_background=False)
        assert dmm._save_and_resume.called

        reset()
        dmm.recover_vm_connectivity(callback, in_background=True)

    def test_save_and_resume(self):
        dmm = MockDockerManager()
        dmm.hypervisor = MockHypervisor()
        dmm._set_docker_machine_env()

        callback = mock.Mock()
        dmm._save_and_resume(callback)
        assert callback.called

    def test_set_docker_machine_env(self):
        dmm = MockDockerManager()
        environ = dict()

        def raise_process_error(*args, **kwargs):
            raise CalledProcessError(-1, "test_command")

        def raise_on_env(key, *args, **kwargs):
            if key == 'env':
                raise_process_error()
            return key

        with mock.patch.dict('os.environ', environ):
            dmm._set_docker_machine_env()
            assert dmm._config_dir == 'tmp'

            with mock.patch.object(dmm, 'command', side_effect=raise_process_error):
                with self.assertRaises(CalledProcessError):
                    dmm._set_docker_machine_env()

            with mock.patch.object(dmm, 'command', side_effect=raise_on_env):
                with self.assertRaises(CalledProcessError):
                    dmm._set_docker_machine_env()


class TestHypervisor(LogTestCase):

    def test_remove(self):
        hypervisor = Hypervisor(MockDockerManager())
        hypervisor.remove('test')

        assert ['rm', 'test', None, False, False] \
            in hypervisor._docker_manager.command_calls

        # errors
        with mock.patch.object(hypervisor._docker_manager, 'command',
                               raise_exception):
            with self.assertLogs(logger, 'WARN'):
                assert not hypervisor.remove('test')

    def test_not_implemented(self):
        hypervisor = Hypervisor(MockDockerManager())

        with self.assertRaises(NotImplementedError):
            hypervisor.constrain(MACHINE_NAME, param_1=1)

        with self.assertRaises(NotImplementedError):
            hypervisor.constraints(MACHINE_NAME)

        with self.assertRaises(NotImplementedError):
            with hypervisor.restart_ctx(MACHINE_NAME):
                pass

        with self.assertRaises(NotImplementedError):
            with hypervisor.recover_ctx(MACHINE_NAME):
                pass

        with self.assertRaises(NotImplementedError):
            hypervisor._new_instance(None)


class TestVirtualBoxHypervisor(LogTestCase):

    def setUp(self):
        self.docker_manager = mock.Mock()
        self.virtualbox = mock.Mock()
        self.ISession = mock.Mock
        self.LockType = mock.Mock()

        self.hypervisor = VirtualBoxHypervisor(self.docker_manager, self.virtualbox,
                                               self.ISession, self.LockType)

    def test_instance(self):
        with mock.patch.dict('sys.modules', **{
            'virtualbox': mock.MagicMock(),
            'virtualbox.library': mock.MagicMock()
        }):
            assert VirtualBoxHypervisor.instance(None)

    def test_save_vm_state(self):
        self.hypervisor._machine_from_arg = mock.Mock()
        self.hypervisor._session_from_arg = lambda o, **_: o
        session = self.hypervisor._save_state(mock.Mock())
        assert session.machine.save_state.called

    def test_restart_ctx(self):
        machine = mock.Mock()
        session = mock.Mock()

        session.machine.state = self.hypervisor.power_down_states[0]
        machine.create_session.return_value = session

        self.hypervisor._machine_from_arg = mock.Mock()
        self.hypervisor._session_from_arg = lambda o, **_: o
        self.hypervisor._machine_from_arg.return_value = machine

        vms = [None]
        with self.hypervisor.restart_ctx(MACHINE_NAME) as vm:
            assert self.hypervisor._docker_manager.stop_docker_machine.called
            assert session.console.power_down.called
            assert machine.create_session.called
            assert vm
            vms[0] = vm

        assert vms[0].save_settings.called
        assert self.hypervisor._docker_manager.start_docker_machine.called

        session.machine.state = None

        vms = [None]
        with self.hypervisor.restart_ctx(MACHINE_NAME) as vm:
            vms[0] = vm
            raise Exception
        assert vms[0].save_settings.called

    def test_recover_ctx(self):
        machine = mock.Mock()
        session = mock.Mock()

        session.machine.state = self.hypervisor.power_down_states[0]
        machine.create_session.return_value = session

        self.hypervisor._machine_from_arg = mock.Mock()
        self.hypervisor._session_from_arg = lambda o, **_: o
        self.hypervisor._machine_from_arg.return_value = machine
        self.hypervisor._save_state = mock.Mock()

        with self.hypervisor.recover_ctx(MACHINE_NAME) as vm:
            assert machine.create_session.called
            assert self.hypervisor._save_state.called
            assert vm

        assert session.unlock_machine.called
        assert self.hypervisor._docker_manager.start_docker_machine.called

    def test_create(self):
        self.hypervisor._docker_manager = MockDockerManager()
        self.hypervisor.create('test')
        assert ['create', 'test', ('--driver', 'virtualbox'), False, False] \
            in self.hypervisor._docker_manager.command_calls

        # errors
        with mock.patch.object(self.hypervisor._docker_manager, 'command',
                               raise_exception):
            with self.assertLogs(logger, 'ERROR'):
                assert not self.hypervisor.create('test')

    def test_constraints(self):
        machine = mock.Mock()
        constraints = dict(
            cpu_count=1,
            memory_size=1024
        )

        self.hypervisor._machine_from_arg = mock.Mock()
        self.hypervisor._machine_from_arg.return_value = machine
        self.hypervisor.constrain(machine, **constraints)

        read = self.hypervisor.constraints(MACHINE_NAME)
        for key, value in constraints.iteritems():
            assert value == read[key]

        # errors
        with mock.patch.object(self.hypervisor, '_machine_from_arg',
                               return_value=Erroneous()):
            with self.assertLogs(logger, 'ERROR'):
                self.hypervisor.constrain(MACHINE_NAME, cpu_count=1)

    def test_session_from_arg(self):
        assert self.hypervisor._session_from_arg(MACHINE_NAME).__class__ is not None
        assert self.virtualbox.find_machine.called

        self.virtualbox.find_machine.called = False

        assert self.hypervisor._session_from_arg(mock.Mock()).__class__ is not None
        assert not self.virtualbox.find_machine.called

    def test_machine_from_arg(self):

        assert self.hypervisor._machine_from_arg(MACHINE_NAME)
        assert self.virtualbox.find_machine.called

        self.virtualbox.find_machine.called = False

        assert self.hypervisor._machine_from_arg(None) is None
        assert not self.virtualbox.find_machine.called

        self.virtualbox.find_machine = lambda *_: raise_exception(
            'Test exception')

        assert not self.hypervisor._machine_from_arg(MACHINE_NAME)

    def test_power_up(self):
        with mock.patch.object(self.hypervisor, '_machine_from_arg') \
                as _mfa:
            assert self.hypervisor.power_up(MACHINE_NAME)
            assert _mfa.called

        with mock.patch.object(self.hypervisor, '_machine_from_arg',
                               raise_exception):
            with self.assertLogs(logger, 'ERROR'):
                assert not self.hypervisor.power_up(MACHINE_NAME)

    def test_power_down(self):
        with mock.patch.object(self.hypervisor, '_session_from_arg') \
                as _sfa:
            assert self.hypervisor.power_down(MACHINE_NAME)
            assert _sfa.called

        with mock.patch.object(self.hypervisor, '_session_from_arg',
                               raise_exception):
            with self.assertLogs(logger, 'ERROR'):
                assert not self.hypervisor.power_down(MACHINE_NAME)


class TestXhyveHypervisor(TempDirFixture, LogTestCase):

    def setUp(self):
        TempDirFixture.setUp(self)
        LogTestCase.setUp(self)

        self.docker_manager = mock.Mock()
        self.virtualbox = mock.Mock()
        self.ISession = mock.Mock()
        self.LockType = mock.Mock()

        self.hypervisor = XhyveHypervisor(self.docker_manager)

    def test_create(self):

        constraints = dict(
            cpu_count=1,
            memory_size=10000
        )

        self.hypervisor._docker_manager = MockDockerManager()
        self.hypervisor.create('test', **constraints)

        assert ['create', 'test', [
            '--driver', 'xhyve',
            self.hypervisor.options['storage'],
            self.hypervisor.options['cpu'], str(constraints['cpu_count']),
            self.hypervisor.options['mem'], str(constraints['memory_size'])
        ], False, False] in self.hypervisor._docker_manager.command_calls

        # errors
        with mock.patch.object(self.hypervisor._docker_manager, 'command',
                               raise_exception):
            with self.assertLogs(logger, 'ERROR'):
                assert not self.hypervisor.create('test')

    def test_constraints(self):

        config = dict(
            cpu_count=4,
            memory_size=4096
        )

        constraints = dict(
            Driver=dict(
                CPU=4,
                Memory=4096
            )
        )

        self.docker_manager.command.return_value = json.dumps(constraints)
        self.docker_manager.config_dir = self.tempdir

        config_dir = os.path.join(self.docker_manager.config_dir,
                                  MACHINE_NAME)
        config_file = os.path.join(config_dir, 'config.json')

        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
        with open(config_file, 'w') as f:
            f.write(json.dumps(constraints))

        self.hypervisor.constrain(MACHINE_NAME, **config)
        assert config == self.hypervisor.constraints(MACHINE_NAME)

        self.hypervisor.constrain(MACHINE_NAME)
        assert config == self.hypervisor.constraints(MACHINE_NAME)

        # errors
        with mock.patch.object(self.hypervisor._docker_manager, 'command',
                               lambda *_: raise_exception(TypeError)):
            with self.assertLogs(logger, 'ERROR'):
                self.hypervisor.constraints(MACHINE_NAME)

    def test_recover_ctx(self):

        with self.hypervisor.recover_ctx(MACHINE_NAME) as name:
            assert name == MACHINE_NAME
            assert self.docker_manager.docker_machine_running.called
            assert self.docker_manager.stop_docker_machine.called
            assert not self.docker_manager.start_docker_machine.called

        assert self.docker_manager.start_docker_machine.called
