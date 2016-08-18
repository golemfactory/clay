import unittest

import mock
from golem.docker.machine.machine_manager import DockerMachineManager

MACHINE_NAME = 'default'


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


class MockDockerMachineManager(DockerMachineManager):

    def __init__(self,
                 use_parent_methods=False,
                 machine_name=None,
                 default_memory_size=1024,
                 default_cpu_execution_cap=100,
                 default_cpu_count=1,
                 min_memory_size=1024,
                 min_cpu_execution_cap=1,
                 min_cpu_count=1):

        super(MockDockerMachineManager, self).__init__(
            machine_name,
            default_memory_size,
            default_cpu_execution_cap,
            default_cpu_count,
            min_memory_size,
            min_cpu_execution_cap,
            min_cpu_count
        )

        self._threads = MockThreadExecutor()
        self.virtual_box = MockVirtualBox()
        self.ISession = MockSession
        self.LockType = MockLockType
        self.set_defaults()
        self.use_parent_methods = use_parent_methods

    def set_defaults(self):
        self.docker_images = [MACHINE_NAME]
        self.docker_machine = MACHINE_NAME
        self.docker_machine_available = True

    def docker_machine_command(self, key, machine_name=None, check_output=True, shell=False):
        if self.use_parent_methods:
            return super(MockDockerMachineManager, self).docker_machine_command(
                key, machine_name, check_output, shell)
        return MACHINE_NAME


class TestDockerMachineManager(unittest.TestCase):

    def test_build_config(self):
        config = MockConfig(0, 768, 512)

        dmm = MockDockerMachineManager()
        assert dmm.virtual_box_config == dmm.defaults

        dmm.build_config(config)
        assert dmm.virtual_box_config != dmm.defaults
        assert len(dmm.virtual_box_config) < len(config.to_dict())

        assert dmm.virtual_box_config.get('cpu_count') == dmm.min_constraints.get('cpu_count')
        assert dmm.virtual_box_config.get('memory_size') == dmm.min_constraints.get('memory_size')

        return dmm.container_host_config, dmm.virtual_box_config

    def test_start_vm(self):
        dmm = MockDockerMachineManager()
        assert dmm.start_vm(MACHINE_NAME)

    def test_stop_vm(self):
        dmm = MockDockerMachineManager()
        assert dmm.stop_vm(MACHINE_NAME)

    def test_check_environment(self):
        dmm = MockDockerMachineManager()

        dmm.check_environment()
        assert dmm.docker_machine_available

        get_images = dmm.docker_machine_images
        dmm.docker_machine_images = lambda x: []

        dmm.check_environment()
        assert not dmm.docker_machine_available

        dmm.docker_machine_images = get_images
        dmm.docker_machine = MACHINE_NAME
        dmm.virtual_box.version = None

        dmm.check_environment()
        assert not dmm.docker_machine_available

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

        host_config, virtualbox_config = self.test_build_config()

        dmm = MockDockerMachineManager()
        dmm.container_host_config = host_config
        dmm.virtual_box_config = virtualbox_config
        dmm.check_environment()
        dmm.set_defaults()

        dmm.update_config(status_cb, done_cb, in_background=False)
        dmm.update_config(status_cb, done_cb, in_background=True)

    def test_docker_machine_command(self):
        dmm = MockDockerMachineManager(use_parent_methods=True)
        dmm.docker_machine_commands['test'] = ['echo', MACHINE_NAME]

        assert dmm.docker_machine_command('test')
        assert dmm.docker_machine_command('test', check_output=False) == 0
        assert not dmm.docker_machine_command('deadbeef')

    def test_start_stop_methods(self):
        dmm = MockDockerMachineManager()

        dmm.docker_machine_commands['start'] = ['echo']
        dmm.docker_machine_commands['stop'] = ['echo']

        dmm._start_docker_machine()
        dmm._stop_docker_machine()

    def test_constrain_all(self):
        dmm = MockDockerMachineManager()
        dmm.constrain_all([MACHINE_NAME])

    def test_recover_vm_connectivity(self):
        callback = mock.Mock()

        dmm = MockDockerMachineManager()
        dmm._save_vm_state = mock.Mock()
        dmm.start_vm = mock.Mock()
        dmm._env_checked = True

        dmm._start_docker_machine = mock.Mock()
        dmm.docker_machine_available = False

        dmm._start_docker_machine.called = False
        dmm.recover_vm_connectivity(callback, in_background=False)
        assert not dmm._start_docker_machine.called

        dmm._start_docker_machine.called = False
        dmm.recover_vm_connectivity(callback, in_background=True)
        assert not dmm._start_docker_machine.called

        dmm.docker_machine_available = True

        callback.called = False
        dmm._start_docker_machine.called = False
        dmm.recover_vm_connectivity(callback, in_background=False)
        assert dmm._start_docker_machine.called
        assert callback.called

        callback.called = False
        dmm._start_docker_machine.called = False
        dmm._threads = mock.Mock()
        dmm._threads.push = lambda x: x.run()
        dmm.recover_vm_connectivity(callback, in_background=True)
        assert dmm._start_docker_machine.called
        assert callback.called

    def test_save_vm_state(self):
        dmm = MockDockerMachineManager()
        assert not dmm._save_vm_state(None)
        assert dmm._save_vm_state(MACHINE_NAME)

    def test_recover_ctx(self):
        dmm = MockDockerMachineManager()

        machine_from_arg = mock.Mock()
        start_docker_machine = mock.Mock()
        save_vm_state = mock.Mock()

        dmm._DockerMachineManager__machine_from_arg = machine_from_arg
        dmm._start_docker_machine = start_docker_machine
        dmm._save_vm_state = save_vm_state

        machine_from_arg.return_value = None

        with dmm._recover_ctx(mock.Mock()):
            pass
        assert not start_docker_machine.called

        session = mock.Mock()
        session.machine.state = 'Running'
        immutable_vm = mock.Mock()
        immutable_vm.create_session.return_value = session
        machine_from_arg.return_value = immutable_vm

        with dmm._recover_ctx(mock.Mock()):
            pass
        assert start_docker_machine.called

        with dmm._recover_ctx(mock.Mock()):
            raise Exception("1")
        assert session.unlock_machine.called

    def test_restart_ctx(self):
        dmm = MockDockerMachineManager()
        machine_from_arg = mock.Mock()
        machine_from_arg.return_value = None
        dmm._DockerMachineManager__machine_from_arg = machine_from_arg
        dmm._docker_machine_running = mock.Mock()
        dmm._start_docker_machine = mock.Mock()
        dmm._stop_vm = mock.Mock()

        with dmm._restart_ctx(mock.Mock()):
            pass
        assert not dmm._docker_machine_running.called

        machine_from_arg.return_value = mock.Mock()
        with dmm._restart_ctx(mock.Mock()):
            raise Exception("X")
        assert dmm._docker_machine_running.called
