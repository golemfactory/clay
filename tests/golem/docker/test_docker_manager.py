# pylint: disable=too-many-lines
import functools
import json
import os
import sys
import types
import uuid
from contextlib import contextmanager
from subprocess import CalledProcessError
from typing import Optional
from unittest import TestCase, mock

from golem.docker.commands.docker_for_mac import DockerForMacCommandHandler
from golem.docker.commands.docker_machine import DockerMachineCommandHandler
from golem.docker.config import DEFAULTS, DOCKER_VM_NAME as VM_NAME, \
    MIN_CONSTRAINTS
from golem.docker.hypervisor import Hypervisor
from golem.docker.hypervisor.docker_for_mac import DockerForMac
from golem.docker.hypervisor.docker_machine import DockerMachineHypervisor
from golem.docker.hypervisor.virtualbox import VirtualBoxHypervisor
from golem.docker.hypervisor.xhyve import XhyveHypervisor
from golem.docker.manager import DockerManager
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


def command(self, key, machine_name=None, args=None, shell=False):
    # pylint: disable=too-many-return-statements
    command_calls = getattr(self, 'command_calls', None)
    if command_calls:
        command_calls.append([key, machine_name, args, shell])

    if getattr(self, 'use_parent_methods', False):
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
        print('>> commands', key, machine_name)
        import traceback
        traceback.print_stack()
        raise KeyError(key)

    return VM_NAME


class MockHypervisor(DockerMachineHypervisor):
    # pylint: disable=method-hidden

    def __init__(self, manager=None, **_kwargs):
        super().__init__(manager or mock.Mock())
        self.recover_ctx = self.ctx
        self.restart_ctx = self.ctx
        self.constrain = mock.Mock()

    @contextmanager
    def ctx(self, name=None, *_):
        yield name

    @staticmethod
    def constraints(*_):
        return dict()

    def create(self, name: Optional[str] = None, **params):
        pass

    def constrain(self, name: Optional[str] = None, **params) -> None:
        pass

    def restart_ctx(self, name: Optional[str] = None):
        self.ctx(name)

    def recover_ctx(self, name: Optional[str] = None):
        self.ctx(name)


class MockDockerManager(DockerManager):
    # pylint: disable=too-few-public-methods

    def __init__(self,
                 use_parent_methods=False,
                 config_desc=None):

        super(MockDockerManager, self).__init__(config_desc)

        self._threads = mock.Mock()
        self._config = dict(DEFAULTS)


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


class TestDockerManager(TestCase):  # pylint: disable=too-many-public-methods

    def test_build_config(self):
        dmm = MockDockerManager()
        assert dmm._config == DEFAULTS

        dmm.build_config(None)

        config_item_list = list(dmm._config.items())
        assert all([val == DEFAULTS[key] for key, val in config_item_list])

        config = MockConfig(0, 1024 * 1024, 512)

        dmm.build_config(config)
        assert len(dmm._config) < len(config.to_dict())
        assert dmm._config != DEFAULTS

        self.assertEqual(dmm._config.get('cpu_count'),
                         MIN_CONSTRAINTS.get('cpu_count'))

        assert dmm._config.get('memory_size') \
            == MIN_CONSTRAINTS.get('memory_size')

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

        hypervisor = mock.Mock()
        hypervisor.constraints.return_value = DEFAULTS

        dmm._select_hypervisor = mock.Mock(return_value=hypervisor)

        with mock.patch.object(dmm, 'command'):
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
        dmm = MockDockerManager(use_parent_methods=True)

        with mock.patch.dict(
            'golem.docker.commands.docker.DockerCommandHandler.commands',
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


class TestHypervisor(LogTestCase):

    def test_status(self):
        hypervisor = MockHypervisor()

        with mock.patch.object(hypervisor, 'command') as cmd:
            hypervisor.vm_running(VM_NAME)
            assert ('status', VM_NAME) == cmd.call_args[0]

        with mock.patch.object(hypervisor, 'command', raise_process_exception):
            with self.assertLogs(level='ERROR'):
                hypervisor.vm_running(VM_NAME)

    def test_start(self):
        hypervisor = MockHypervisor()

        with mock.patch.object(hypervisor, 'command') as cmd:
            hypervisor.start_vm(VM_NAME)
            assert ('start', VM_NAME) == cmd.call_args[0]

        with mock.patch.object(hypervisor, 'command', raise_process_exception):
            with self.assertRaises(CalledProcessError):
                hypervisor.start_vm(VM_NAME)

    def test_stop(self):
        hypervisor = MockHypervisor()

        with mock.patch.object(hypervisor, 'command') as cmd:
            hypervisor.stop_vm(VM_NAME)
            assert ('stop', VM_NAME) == cmd.call_args[0]

        with mock.patch.object(hypervisor, 'command', raise_process_exception):
            with self.assertLogs(level='WARN'):
                hypervisor.stop_vm(VM_NAME)

    def test_vm_not_running(self):
        hypervisor = MockHypervisor(mock.Mock())
        hypervisor._docker_vm = str(uuid.uuid4())
        assert not hypervisor.vm_running()

    def test_vm_running(self):
        hypervisor = MockHypervisor(mock.Mock())
        hypervisor._docker_vm = VM_NAME

        with mock.patch.object(
            hypervisor, 'command',
            side_effect=functools.partial(command, hypervisor)
        ):
            assert hypervisor.vm_running()

    def test_remove(self):
        hypervisor = MockHypervisor()

        with mock.patch.object(hypervisor, 'command') as cmd:
            hypervisor.remove('test')
            assert ('rm', 'test') == cmd.call_args[0]

        # errors
        with mock.patch.object(hypervisor, 'command', raise_process_exception):
            with self.assertLogs(level='WARN'):
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
        self.hypervisor._set_env = mock.Mock()
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
        self.hypervisor._set_env = mock.Mock()
        self.hypervisor.start_vm = mock.Mock()
        self.hypervisor.stop_vm = mock.Mock()

        with self.hypervisor.recover_ctx(VM_NAME) as vm:
            assert vm
            assert machine.create_session.called
            assert self.hypervisor._save_state.called

        assert session.unlock_machine.called
        assert self.hypervisor.start_vm.called

    def test_create(self):

        with mock.patch.object(self.hypervisor, 'command') as cmd:
            self.hypervisor.create('test')
            assert ('create', 'test') == cmd.call_args[0]
            assert {'args': ('--driver', 'virtualbox')} == cmd.call_args[1]

        # errors
        with mock.patch.object(self.hypervisor, 'command',
                               raise_process_exception):
            with self.assertLogs(level='ERROR'):
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
            with self.assertLogs(level='ERROR'):
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
            with self.assertLogs(level='ERROR'):
                assert not self.hypervisor.power_up(VM_NAME)

    def test_power_down(self):
        with mock.patch.object(self.hypervisor, '_session_from_arg') \
                as _sfa:
            assert self.hypervisor.power_down(VM_NAME)
            assert _sfa.called

        with mock.patch.object(self.hypervisor, '_session_from_arg',
                               raise_exception):
            with self.assertLogs(level='ERROR'):
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
        self.hypervisor.command_calls = []
        self.hypervisor.command = types.MethodType(command, self.hypervisor)

    def test_create(self):

        constraints = dict(
            cpu_count=1,
            memory_size=10000
        )
        expected_args = (
            self.hypervisor.options['storage'],
            self.hypervisor.options['cpu'], str(constraints['cpu_count']),
            self.hypervisor.options['mem'], str(constraints['memory_size'])
        )

        with mock.patch.object(self.hypervisor, 'command') as cmd:
            self.hypervisor.create('test', **constraints)

        assert ('create', 'test') == cmd.call_args[0]

        args = cmd.call_args[1]['args']
        assert all(a in args for a in expected_args)

        # errors
        with mock.patch.object(self.hypervisor, 'command',
                               raise_process_exception):
            with self.assertLogs(level='ERROR'):
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

        with mock.patch.object(self.hypervisor, 'command',
                               return_value=constraints_str):

            self.hypervisor.constrain(**config)
            assert config == self.hypervisor.constraints(VM_NAME)

            self.hypervisor.constrain()
            assert config == self.hypervisor.constraints(VM_NAME)

        # errors
        with mock.patch.object(self.hypervisor, 'command',
                               lambda *_: raise_exception(TypeError)):
            with self.assertLogs(level='ERROR'):
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


class TestDockerForMacHypervisor(TempDirFixture):

    HANDLER = 'golem.docker.commands.docker_for_mac.DockerForMacCommandHandler'

    def test_setup_when_running(self):
        # pylint: disable=no-member

        docker_manager = DockerManager()
        hypervisor = DockerForMac(docker_manager)
        docker_manager.hypervisor = hypervisor

        with mock.patch(f'{self.HANDLER}.status', return_value='Running'):
            with mock.patch(f'{self.HANDLER}.wait_until_started') as wait:
                with mock.patch(f'{self.HANDLER}.start') as start:

                    hypervisor.setup()

                    assert wait.called
                    assert not start.called

    def test_setup_when_not_running(self):
        # pylint: disable=no-member

        docker_manager = DockerManager()
        hypervisor = DockerForMac(docker_manager)
        docker_manager.hypervisor = hypervisor

        with mock.patch(f'{self.HANDLER}.status', return_value=''):
            with mock.patch(f'{self.HANDLER}.wait_until_started') as wait:
                with mock.patch(f'{self.HANDLER}.start') as start:

                    hypervisor.setup()

                    assert not wait.called
                    assert start.called

    def test_is_available(self):

        hypervisor = DockerForMac.instance(mock.Mock())

        app_existing = self.tempdir
        app_missing = os.path.join(self.tempdir, str(uuid.uuid4()))

        with mock.patch(f'{self.HANDLER}.APP', app_existing):
            assert hypervisor.is_available()

        with mock.patch(f'{self.HANDLER}.APP', app_missing):
            assert not hypervisor.is_available()

    def test_create(self):

        hypervisor = DockerForMac.instance(mock.Mock())

        assert not hypervisor.create()
        assert not hypervisor.create("golem")
        assert not hypervisor.create("other name")
        assert not hypervisor.create("other name", cpus=[0, 1, 2])

    def test_remove(self):

        hypervisor = DockerForMac.instance(mock.Mock())

        assert not hypervisor.remove()
        assert not hypervisor.remove("golem")
        assert not hypervisor.remove("other name")

    def test_constrain(self):

        hypervisor = DockerForMac.instance(mock.Mock())

        update_dict = dict(cpu_count=3, memory_size=2048)
        config_file = os.path.join(self.tempdir, 'config_file.json')

        with open(config_file, 'w') as f:
            json.dump(dict(), f)

        with mock.patch.object(hypervisor, 'CONFIG_FILE', config_file):
            hypervisor.constrain(**update_dict)
            assert hypervisor.constraints() == update_dict


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
                                   '_pid', return_value=1234):

                DockerForMacCommandHandler.stop()
                assert wait.called

    def test_stop_failure(self, check_call, _):
        check_call.side_effect = CalledProcessError(1, [])

        with mock.patch(f'{self.PKG_PATH}.wait_until_stopped') as wait:
            with mock.patch.object(DockerForMacCommandHandler,
                                   '_pid', return_value=1234):

                DockerForMacCommandHandler.stop()
                assert not wait.called

    def test_status(self, *_):

        with mock.patch(f'{self.PKG_PATH}._pid', return_value=1234):
            assert DockerForMacCommandHandler.status() == 'Running'

        with mock.patch(f'{self.PKG_PATH}._pid', return_value=None):
            assert DockerForMacCommandHandler.status() == ''

    def test_pid(self, _, popen):

        stdout, stderr = mock.Mock(), mock.Mock()
        popen.return_value = mock.Mock(communicate=mock.Mock(
            return_value=(stdout, stderr)
        ))

        stdout.strip.return_value = b'user 1234'
        assert DockerForMacCommandHandler._pid() == 1234

        stdout.strip.return_value = b''
        assert DockerForMacCommandHandler._pid() is None
