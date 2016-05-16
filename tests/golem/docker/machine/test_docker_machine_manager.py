import unittest
from threading import Thread

import mock
import time

from golem.docker.machine.machine_manager import DockerMachineManager, ThreadExecutor

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
            machine = MockMachine()
            machine.name = MACHINE_NAME
            return machine
        return None


class MockConsole(mock.MagicMock):
    def __init__(self, *args, **kw):
        super(MockConsole, self).__init__(*args, **kw)


class MockSession(mock.MagicMock):
    def __init__(self, *args, **kw):
        super(MockSession, self).__init__(*args, **kw)


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

    def create_session(self, lock_type=MockLockType.null):
        session = MockSession()
        session.console = MockConsole()
        session.machine = self


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
        self.docker_images = [MACHINE_NAME]
        self.docker_machine_available = True

    def docker_machine_command(self, key, check_output=True, shell=False, *args):
        return MACHINE_NAME

    def _apply_constraints(self, vm, params, force=False):
        return True

    def _restart_ctx(self, name_or_id_or_machine, restart=True):
        yield True


class TestThread(Thread):

    def __init__(self, secs, sleep=0.5, group=None,
                 target=None, name=None, args=(),
                 kwargs=None, verbose=None):

        super(TestThread, self).__init__(group, target, name,
                                         args, kwargs, verbose)
        self.working = True
        self.sleep = sleep
        self.secs = secs
        self.called = False

    def run(self):
        self.called = True
        start = time.time()
        while self.working:
            time.sleep(self.sleep)
            if time.time() - start >= self.secs:
                break


class TestThreadExecutor(unittest.TestCase):

    def test_queue(self):
        executor = ThreadExecutor()
        executor.start()

        j1 = TestThread(30)
        j2 = TestThread(30)
        j3 = TestThread(30)

        executor.push(j1)
        assert len(executor._threads) == 1
        executor.push(j2)
        assert len(executor._threads) == 2
        executor.push(j3)
        assert len(executor._threads) == 2
        assert j2 not in executor._threads

        j1.working = False
        j2.working = False
        j3.working = False
        executor.working = False

    def test_order(self):
        executor = ThreadExecutor()
        executor.start()

        j1 = TestThread(0)
        j2 = TestThread(0)

        executor.push(j1)
        executor.push(j2)

        time.sleep(2)

        assert j1.called
        assert j2.called

        j1.working = False
        j2.working = False
        executor.working = False


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

    def start_vm(self):
        dmm = MockDockerMachineManager()
        assert dmm.start_vm()

    def stop_vm(self):
        dmm = MockDockerMachineManager()
        assert dmm.stop_vm()

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

        dmm._env_checked = True
        dmm.docker_machine = 'default'
        dmm.update_config(status_cb, done_cb, in_background=False)
        dmm.update_config(status_cb, done_cb, in_background=True)











