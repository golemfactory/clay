import functools
import json
import os
import uuid
from contextlib import contextmanager
from subprocess import CalledProcessError
from typing import Optional, Dict
from unittest import mock, TestCase, skipIf

from golem.core.common import is_osx, is_windows
from golem.docker.commands.docker_machine import DockerMachineCommandHandler
from golem.docker.config import DOCKER_VM_NAME as VM_NAME, DEFAULTS
from golem.docker.hypervisor.docker_for_mac import DockerForMac
from golem.docker.hypervisor.docker_machine import DockerMachineHypervisor
from golem.docker.hypervisor.dummy import DummyHypervisor
from golem.docker.hypervisor.virtualbox import VirtualBoxHypervisor
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
        self.reconfig_ctx = self.ctx
        self.constrain = mock.Mock()

    @classmethod
    def is_available(cls) -> bool:
        return True

    @contextmanager
    def ctx(self, name=None, *_):
        yield name

    def constraints(self, name: Optional[str] = None) -> Dict:
        return dict()

    def create(self, vm_name: Optional[str] = None, **params) -> bool:
        return True

    def constrain(self, name: Optional[str] = None, **params) -> None:
        pass


class MockDockerManager(DockerManager):
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

    @mock.patch('golem.docker.hypervisor.docker_machine.local_client')
    def test_get_port_mapping(self, local_client):
        local_client().inspect_container.return_value = {
            'NetworkSettings': {
                'Ports': {
                    '12345/tcp': [{
                        'HostIp': '0.0.0.0',
                        'HostPort': '54321'
                    }]
                }
            }
        }
        hypervisor = MockHypervisor()
        vm_ip = '192.168.64.151'
        cmd_out = vm_ip + '\n'
        with mock.patch.object(hypervisor, 'command', return_value=cmd_out):
            host, port = hypervisor.get_port_mapping('container_id', 12345)
        self.assertEqual(host, vm_ip)
        self.assertEqual(port, 54321)


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

    def test_reconfig_ctx(self):
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
        with self.hypervisor.reconfig_ctx(VM_NAME) as vm:
            assert self.hypervisor.stop_vm.called
            assert session.console.power_down.called
            assert machine.create_session.called
            assert vm
            vms[0] = vm

        assert vms[0].save_settings.called
        assert self.hypervisor.start_vm.called

        session.machine.state = None

        vms = [None]
        with self.hypervisor.reconfig_ctx(VM_NAME) as vm:
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
            assert {'args': ['--driver', 'virtualbox']} == cmd.call_args[1]

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

    def test_configure_daemon_initial(self):
        hypervisor = DockerForMac.instance(mock.Mock())
        config_file = os.path.join(self.tempdir, 'daemon.json')

        with mock.patch.object(hypervisor, 'DAEMON_CONFIG_FILE', config_file):
            hypervisor._configure_daemon()
            self._assert_dns_configured(config_file)

    def test_configure_daemon_update(self):
        hypervisor = DockerForMac.instance(mock.Mock())
        config_file = os.path.join(self.tempdir, 'daemon.json')

        with mock.patch.object(hypervisor, 'DAEMON_CONFIG_FILE', config_file):
            extra_settings = {'option': ['value1', 'value2']}
            with open(config_file, 'w') as f:
                json.dump(extra_settings, f)

            hypervisor._configure_daemon()
            config = self._assert_dns_configured(config_file)
            assert 'option' in config
            assert config['option'] == extra_settings['option']

    @staticmethod
    def _assert_dns_configured(config_file) -> Dict:
        with open(config_file, 'r') as f:
            daemon_config = json.load(f)

        assert 'dns' in daemon_config
        assert daemon_config['dns']
        assert all(daemon_config['dns'])

        return daemon_config

    @mock.patch('golem.docker.hypervisor.docker_for_mac.local_client')
    def test_get_port_mapping(self, local_client):
        local_client().inspect_container.return_value = {
            'NetworkSettings': {
                'Ports': {
                    '12345/tcp': [{
                        'HostIp': '0.0.0.0',
                        'HostPort': '54321'
                    }]
                }
            }
        }
        hypervisor = DockerForMac.instance(mock.Mock())
        host, port = hypervisor.get_port_mapping('container_id', 12345)
        self.assertEqual(host, '127.0.0.1')
        self.assertEqual(port, 54321)


@skipIf(is_windows(), 'Linux & macOS only')
class TestDummyHypervisor(TestCase):

    @mock.patch('golem.docker.hypervisor.dummy.local_client')
    def test_get_port_mapping(self, local_client):
        container_ip = '172.17.0.2'
        local_client().inspect_container.return_value = {
            'NetworkSettings': {
                'Networks': {
                    'bridge': {
                        'IPAddress': container_ip,
                    }
                },
                'Ports': {
                    '12345/tcp': [{
                        'HostPort': 12345,
                    }]
                }
            }
        }

        hypervisor = DummyHypervisor(mock.Mock())
        host, port = hypervisor.get_port_mapping('container_id', 12345)

        self.assertEqual(port, 12345)
        if is_osx():
            self.assertEqual(host, '127.0.0.1')
        else:
            self.assertEqual(host, container_ip)
