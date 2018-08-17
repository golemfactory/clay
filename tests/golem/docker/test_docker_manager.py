import json
import os
import sys
import unittest
import uuid
from unittest import mock
from contextlib import contextmanager
from subprocess import CalledProcessError

from golem.docker.manager import DockerManager, DOCKER_VM_NAME as VM_NAME, \
    VirtualBoxHypervisor, XhyveHypervisor, \
    Hypervisor, logger, DockerMachineCommandHandler, DockerMachineHypervisor
from golem.testutils import TempDirFixture
from golem.tools.assertlogs import LogTestCase


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
        if name == VM_NAME:
            return MockMachine(name=VM_NAME)
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


class MockHypervisor(DockerMachineHypervisor):

    def __init__(self, manager=None, **_kwargs):
        super().__init__(manager)
        self.recover_ctx = self.ctx
        self.restart_ctx = self.ctx
        self.constrain = mock.Mock()

    @contextmanager
    def ctx(self, name=None, *_):
        yield name

    @staticmethod
    def constraints(*_):
        return dict()


class MockDockerManager(DockerManager):

    def __init__(self,
                 use_parent_methods=False,
                 config_desc=None):

        super(MockDockerManager, self).__init__(config_desc)

        self.command_calls = []

        self._threads = MockThreadExecutor()
        self._config = dict(self.defaults)
        self.use_parent_methods = use_parent_methods

    def command(self, key, machine_name=None, args=None, shell=False):
        self.command_calls.append([key, machine_name, args, shell])

        if self.use_parent_methods:
            tmp_super = super(MockDockerManager, self)
            return tmp_super.command(key, machine_name=machine_name, args=args,
                                     shell=shell)
        elif key == 'env':
            return '\n'.join([
                'SET GOLEM_TEST=1',
                '',
                'INVALID DOCKER=2',
                'SET DOCKER_CERT_PATH="{}"'.format(
                    os.path.join('tmp', 'golem'))
            ])
        elif key == 'list':
            return VM_NAME
        elif key == 'status':
            return 'Running'
        elif key == 'version':
            return '1.0.0'
        elif key == 'help':
            return '[help contents]'
        elif key == 'regenerate_certs':
            return 'certs'
        elif key not in DockerMachineCommandHandler.commands:
            raise KeyError(key)

        return VM_NAME


def raise_exception(msg, *args, **kwargs):
    raise TypeError(msg)


def raise_process_exception(msg, *args, **kwargs):
    raise CalledProcessError(1, msg)


class Erroneous(mock.Mock):

    @property
    def cpu_count(self):
        raise_exception("Read")

    @cpu_count.setter
    def cpu_count(self, value):
        raise_exception("Write")


class TestDockerManager(unittest.TestCase):

    def test_status(self):
        dmm = MockDockerManager()
        dmm.hypervisor = DockerMachineHypervisor(dmm)
        dmm.hypervisor.vm_running(VM_NAME)
        assert ['status', VM_NAME, None, False] in dmm.command_calls

        with mock.patch.object(dmm, 'command', raise_process_exception):
            with self.assertLogs(logger, 'ERROR'):
                dmm.hypervisor.vm_running(VM_NAME)

    def test_start(self):
        dmm = MockDockerManager()
        dmm.hypervisor = DockerMachineHypervisor(dmm)
        dmm.hypervisor.start_vm(VM_NAME)
        assert ['start', VM_NAME, None, False] in dmm.command_calls

        with mock.patch.object(dmm, 'command', raise_process_exception):
            with self.assertRaises(CalledProcessError):
                dmm.hypervisor.start_vm(VM_NAME)

    def test_stop(self):
        dmm = MockDockerManager()
        dmm.hypervisor = DockerMachineHypervisor(dmm)
        dmm.hypervisor.stop_vm(VM_NAME)
        assert ['stop', VM_NAME, None, False] in dmm.command_calls

        with mock.patch.object(dmm, 'command', raise_process_exception):
            with self.assertLogs(logger, 'WARN'):
                dmm.hypervisor.stop_vm(VM_NAME)

    def test_vm_not_running(self):
        hypervisor = DockerMachineHypervisor(mock.Mock())
        hypervisor._docker_vm = str(uuid.uuid4())
        assert not hypervisor.vm_running()

    def test_vm_running(self):
        docker_manager = mock.Mock(command=mock.Mock(return_value='Running'))
        hypervisor = DockerMachineHypervisor(docker_manager)
        hypervisor._docker_vm = VM_NAME
        assert hypervisor.vm_running()

    def test_build_config(self):
        dmm = MockDockerManager()
        assert dmm._config == dmm.defaults

        dmm.build_config(None)

        config_item_list = list(dmm._config.items())
        assert all([val == dmm.defaults[key] for key, val in config_item_list])

        config = MockConfig(0, 1024 * 1024, 512)

        dmm.build_config(config)
        assert len(dmm._config) < len(config.to_dict())
        assert dmm._config != dmm.defaults

        self.assertEqual(dmm._config.get('cpu_count'),
                         dmm.min_constraints.get('cpu_count'))

        assert dmm._config.get('memory_size') \
            == dmm.min_constraints.get('memory_size')

        config = MockConfig(10, 10000 * 1024, 20000)

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

        def done_cb(_):
            pass

        config = MockConfig(0, 768, 512)

        dmm = MockDockerManager()
        dmm.pull_images = mock.Mock()
        dmm.build_images = mock.Mock()
        dmm.hypervisor = mock.Mock()
        dmm.hypervisor.constraints.return_value = dmm.defaults

        dmm.build_config(config)
        dmm.check_environment()

        dmm.update_config(status_cb, done_cb, in_background=False)
        dmm.update_config(status_cb, done_cb, in_background=True)

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

        args, kwargs = dmm.hypervisor.constrain.call_args_list.pop()

        assert len(kwargs) == len(diff)
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
        new = dict(
            cpu_count=dmm.defaults['cpu_count'] + 1, unknown_key='value'
        )
        expected = dict(cpu_count=dmm.defaults['cpu_count'] + 1)
        assert diff(old, new) == expected

    def test_command(self):
        dmm = MockDockerManager(use_parent_methods=True)

        with mock.patch.dict(
            'golem.docker.commands.DockerCommandHandler.commands',
            dict(test=[sys.executable, '--version'])
        ):
            assert dmm.command('test').startswith('Python')
            assert not dmm.command('deadbeef')

    @mock.patch('golem.docker.manager.DockerForMac.is_available',
                return_value=False)
    @mock.patch('golem.docker.manager.VirtualBoxHypervisor.instance')
    @mock.patch('golem.docker.manager.XhyveHypervisor.instance')
    def test_get_hypervisor(self, xhyve_instance, virtualbox_instance, _):

        def reset():
            xhyve_instance.called = False
            virtualbox_instance.called = False

        dmm = MockDockerManager()

        with mock.patch('golem.docker.manager.is_windows',
                        return_value=True):

            assert dmm._select_hypervisor()
            assert virtualbox_instance.called
            assert not xhyve_instance.called

        reset()

        with mock.patch('golem.docker.manager.is_windows',
                        return_value=False):
            with mock.patch('golem.docker.manager.is_osx',
                            return_value=True):

                assert dmm._select_hypervisor()
                assert not virtualbox_instance.called
                assert xhyve_instance.called

        reset()

        with mock.patch('golem.docker.manager.is_windows',
                        return_value=False):
            with mock.patch('golem.docker.manager.is_osx',
                            return_value=False):

                assert not dmm._select_hypervisor()
                assert not virtualbox_instance.called
                assert not xhyve_instance.called

    @mock.patch('golem.docker.manager.is_windows', return_value=True)
    @mock.patch('golem.docker.manager.is_linux', return_value=False)
    @mock.patch('golem.docker.manager.is_osx', return_value=False)
    def test_check_environment_windows(self, *_):
        dmm = MockDockerManager()
        dmm.pull_images = mock.Mock()
        dmm.build_images = mock.Mock()

        with mock.patch('golem.docker.manager.VirtualBoxHypervisor.instance',
                        mock.Mock(vm_running=mock.Mock(return_value=False))):

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

        assert pulls[0] == 4

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

        assert builds[0] == 4
        assert tags[0] == 4
        assert len(os_chdir.mock_calls) == 8

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
        dmm.hypervisor._set_env_from_output = mock.Mock()
        dmm.hypervisor._set_env()

        callback = mock.Mock()
        dmm._save_and_resume(callback)
        assert callback.called

    def test_set_env(self):
        dmm = MockDockerManager()
        dmm.hypervisor = MockHypervisor(dmm)
        environ = dict()

        def raise_on_env(key, *args, **kwargs):
            if key == 'env':
                raise_process_exception('error')
            return key

        def raise_not_start(key, *args, **kwargs):
            if key != 'start':
                raise_process_exception('error')
            return key

        with mock.patch.dict('os.environ', environ):
            dmm.hypervisor._set_env()
            assert dmm.hypervisor._config_dir == 'tmp'

            with mock.patch.object(dmm, 'command',
                                   side_effect=raise_process_exception):
                with self.assertRaises(CalledProcessError):
                    dmm.hypervisor._set_env()

            with mock.patch.object(dmm, 'command', side_effect=raise_on_env):
                with self.assertRaises(CalledProcessError):
                    dmm.hypervisor._set_env()

            with mock.patch.object(dmm, 'command', side_effect=raise_not_start):
                with self.assertRaises(CalledProcessError):
                    dmm.hypervisor._set_env()


class TestHypervisor(LogTestCase):

    def test_remove(self):
        hypervisor = Hypervisor(MockDockerManager())
        hypervisor.remove('test')

        assert ['rm', 'test', None, False] \
            in hypervisor._docker_manager.command_calls

        # errors
        with mock.patch.object(hypervisor._docker_manager, 'command',
                               raise_process_exception):
            with self.assertLogs(logger, 'WARN'):
                assert not hypervisor.remove('test')

    def test_not_implemented(self):
        hypervisor = Hypervisor(MockDockerManager())

        with self.assertRaises(NotImplementedError):
            hypervisor.constrain(VM_NAME, param_1=1)

        with self.assertRaises(NotImplementedError):
            hypervisor.constraints(VM_NAME)

        with self.assertRaises(NotImplementedError):
            with hypervisor.restart_ctx(VM_NAME):
                pass

        with self.assertRaises(NotImplementedError):
            with hypervisor.recover_ctx(VM_NAME):
                pass

        with self.assertRaises(NotImplementedError):
            hypervisor._new_instance(None)


class TestVirtualBoxHypervisor(LogTestCase):

    def setUp(self):
        self.docker_manager = mock.Mock()
        self.virtualbox = mock.Mock()
        self.ISession = mock.Mock
        self.LockType = mock.Mock()

        self.hypervisor = VirtualBoxHypervisor(self.docker_manager,
                                               self.virtualbox,
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

        self.hypervisor._machine_from_arg = mock.Mock(return_value=machine)
        self.hypervisor._session_from_arg = lambda o, **_: o
        self.hypervisor._set_env_from_output = mock.Mock()
        self.hypervisor.start_vm = mock.Mock()
        self.hypervisor.stop_vm = mock.Mock()
        self.hypervisor.vm_running = mock.Mock(return_value=True)

        vms = [None]
        with self.hypervisor.restart_ctx(VM_NAME) as vm:
            assert self.hypervisor.stop_vm.called
            assert session.console.power_down.called
            assert machine.create_session.called
            assert vm
            vms[0] = vm

        assert vms[0].save_settings.called
        assert self.hypervisor.start_vm.called

        session.machine.state = None

        vms = [None]
        with self.hypervisor.restart_ctx(VM_NAME) as vm:
            vms[0] = vm
            raise Exception
        assert vms[0].save_settings.called

    def test_recover_ctx(self):
        machine = mock.Mock()
        session = mock.Mock()

        session.machine.state = self.hypervisor.running_states[0]
        machine.create_session.return_value = session

        self.hypervisor._machine_from_arg = mock.Mock(return_value=machine)
        self.hypervisor._session_from_arg = lambda o, **_: o
        self.hypervisor._save_state = mock.Mock()
        self.hypervisor._set_env_from_output = mock.Mock()
        self.hypervisor.start_vm = mock.Mock()
        self.hypervisor.stop_vm = mock.Mock()

        with self.hypervisor.recover_ctx(VM_NAME) as vm:
            assert vm
            assert machine.create_session.called
            assert self.hypervisor._save_state.called

        assert session.unlock_machine.called
        assert self.hypervisor.start_vm.called

    def test_create(self):
        self.hypervisor._docker_manager = MockDockerManager()
        self.hypervisor.create('test')
        assert ['create', 'test', ('--driver', 'virtualbox'), False] \
            in self.hypervisor._docker_manager.command_calls

        # errors
        with mock.patch.object(self.hypervisor._docker_manager, 'command',
                               raise_process_exception):
            with self.assertLogs(logger, 'ERROR'):
                assert not self.hypervisor.create('test')

    def test_constraints(self):
        machine = mock.Mock()
        constraints = dict(
            cpu_count=1,
            memory_size=1024
        )

        self.hypervisor._machine_from_arg = mock.Mock(return_value=machine)
        self.hypervisor.constrain(**constraints)

        read = self.hypervisor.constraints(VM_NAME)
        for key, value in list(constraints.items()):
            assert value == read[key]

        # errors
        with mock.patch.object(self.hypervisor, '_machine_from_arg',
                               return_value=Erroneous()):
            with self.assertLogs(logger, 'ERROR'):
                self.hypervisor.constrain(VM_NAME, cpu_count=1)

    def test_session_from_arg(self):
        assert self.hypervisor._session_from_arg(VM_NAME).__class__ \
            is not None
        assert self.virtualbox.find_machine.called

        self.virtualbox.find_machine.called = False

        assert self.hypervisor._session_from_arg(mock.Mock()).__class__ \
            is not None
        assert not self.virtualbox.find_machine.called

    def test_machine_from_arg(self):

        assert self.hypervisor._machine_from_arg(VM_NAME)
        assert self.virtualbox.find_machine.called

        self.virtualbox.find_machine.called = False

        assert self.hypervisor._machine_from_arg(None) is None
        assert not self.virtualbox.find_machine.called

        self.virtualbox.find_machine = lambda *_: raise_exception(
            'Test exception')

        assert not self.hypervisor._machine_from_arg(VM_NAME)

    def test_power_up(self):
        with mock.patch.object(self.hypervisor, '_machine_from_arg') \
                as _mfa:
            assert self.hypervisor.power_up(VM_NAME)
            assert _mfa.called

        with mock.patch.object(self.hypervisor, '_machine_from_arg',
                               raise_exception):
            with self.assertLogs(logger, 'ERROR'):
                assert not self.hypervisor.power_up(VM_NAME)

    def test_power_down(self):
        with mock.patch.object(self.hypervisor, '_session_from_arg') \
                as _sfa:
            assert self.hypervisor.power_down(VM_NAME)
            assert _sfa.called

        with mock.patch.object(self.hypervisor, '_session_from_arg',
                               raise_exception):
            with self.assertLogs(logger, 'ERROR'):
                assert not self.hypervisor.power_down(VM_NAME)


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
        ], False] in self.hypervisor._docker_manager.command_calls

        # errors
        with mock.patch.object(self.hypervisor._docker_manager, 'command',
                               raise_process_exception):
            with self.assertLogs(logger, 'ERROR'):
                assert not self.hypervisor.create('test')

    def test_constraints(self):

        config = dict(
            cpu_count=4,
            memory_size=4096
        )

        constraints = dict(
            Driver=dict(
                CPU="4",
                Memory="4096",
            )
        )

        constraints_str = str(constraints).replace('\'', '"')

        self.hypervisor._config_dir = self.tempdir
        self.hypervisor._docker_vm = VM_NAME

        config_dir = os.path.join(self.hypervisor._config_dir, VM_NAME)
        config_file = os.path.join(config_dir, 'config.json')

        os.makedirs(config_dir, exist_ok=True)
        with open(config_file, 'w') as f:
            json.dump(constraints, f)

        with mock.patch.object(self.hypervisor._docker_manager, 'command',
                               mock.Mock(return_value=constraints_str)):

            self.hypervisor.constrain(**config)
            assert config == self.hypervisor.constraints(VM_NAME)

            self.hypervisor.constrain()
            assert config == self.hypervisor.constraints(VM_NAME)

        # errors
        with mock.patch.object(self.hypervisor._docker_manager, 'command',
                               lambda *_: raise_exception(TypeError)):
            with self.assertLogs(logger, 'ERROR'):
                self.hypervisor.constraints(VM_NAME)

    def test_recover_ctx(self):
        self.hypervisor.vm_running = mock.Mock()
        self.hypervisor.stop_vm = mock.Mock()
        self.hypervisor.start_vm = mock.Mock()
        self.hypervisor._set_env_from_output = mock.Mock()

        with self.hypervisor.recover_ctx(VM_NAME) as name:
            assert name == VM_NAME
            assert self.hypervisor.vm_running.called
            assert self.hypervisor.stop_vm.called
        assert self.hypervisor.start_vm.called
