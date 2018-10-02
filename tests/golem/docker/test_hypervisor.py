import functools
import json
import os
import types
import uuid
from contextlib import contextmanager
from subprocess import CalledProcessError
from typing import Optional, Dict
from unittest import mock

from golem.docker.commands.docker_machine import DockerMachineCommandHandler
from golem.docker.config import DOCKER_VM_NAME as VM_NAME, DEFAULTS
from golem.docker.hypervisor import Hypervisor
from golem.docker.hypervisor.docker_for_mac import DockerForMac
from golem.docker.hypervisor.docker_machine import DockerMachineHypervisor
from golem.docker.hypervisor.virtualbox import VirtualBoxHypervisor
from golem.docker.hypervisor.xhyve import XhyveHypervisor
from golem.docker.manager import DockerManager
from golem.testutils import TempDirFixture
from golem.tools.assertlogs import LogTestCase


def command(self, key, machine_name=None, args=None, shell=False):
    # pylint: disable=too-many-return-statements
    command_calls = getattr(self, 'command_calls', None)
    if command_calls:
        command_calls.append([key, machine_name, args, shell])

    if key == 'env':
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

    def constraints(self, name: Optional[str] = None) -> Dict:
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
    # pylint: disable=too-many-instance-attributes

    def __init__(self, config_desc=None) -> None:

        super(MockDockerManager, self).__init__(config_desc)

        self._threads = mock.Mock()
        self._config = dict(DEFAULTS)


def raise_exception(msg, *_a, **_kw):
    raise TypeError(msg)


def raise_process_exception(msg, *_a, **_kw):
    raise CalledProcessError(1, msg)


class Erroneous(mock.Mock):

    @property
    def cpu_count(self):
        raise_exception("Read")

    @cpu_count.setter
    def cpu_count(self, _):
        raise_exception("Write")


class TestDockerMachineHypervisor(LogTestCase):

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
        hypervisor._vm_name = str(uuid.uuid4())
        assert not hypervisor.vm_running()

    def test_vm_running(self):
        hypervisor = MockHypervisor(mock.Mock())
        hypervisor._vm_name = VM_NAME

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
        self.hypervisor._vm_name = VM_NAME

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
