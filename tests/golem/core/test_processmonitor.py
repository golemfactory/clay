import os
import subprocess
import time
from multiprocessing import Process


import subprocess
import psutil
from mock import Mock, patch

from golem.core.processmonitor import ProcessMonitor
from golem.tools.assertlogs import LogTestCase


class MockProcess(object):
    def __init__(self, timeout=10, raise_exc=True):
        self.timeout = timeout
        self.working = True
        self.raise_exc = raise_exc

    def run(self):
        started = time.time()

        while self.working:
            time.sleep(1)
            if time.time() - started >= self.timeout:
                if self.raise_exc:
                    raise Exception("Mock process running for over {}s".format(
                        self.timeout))
                else:
                    self.working = False


def wait_for_processes(timeout=10, *processes):
    started = time.time()
    timeout = max(timeout, 5)

    while time.time() - started < timeout:

        all_stopped = True
        for process in processes:
            if ProcessMonitor.is_process_alive(process):
                all_stopped = False
                break

        if all_stopped:
            return
        time.sleep(0.5)


def sleep_1sec():
    time.sleep(1)


def run_exit():
    return


class TestProcessMonitor(LogTestCase):

    def test_monitor(self):
        mp = MockProcess()
        p1 = Process(target=run_exit)
        p2 = Process(target=mp.run)

        p1.start()
        p2.start()

        pm = ProcessMonitor(p1, p2)
        pm.add_callbacks(pm.kill_processes, pm.exit)
        pm.start()

        wait_for_processes(10, p1, p2)

        self.assertFalse(pm.is_process_alive(p1))
        self.assertFalse(pm.is_process_alive(p2))

    def test_monitor_2(self):
        mp1, mp2 = MockProcess(), MockProcess(timeout=0)

        p1 = Process(target=mp1.run)
        p2 = Process(target=mp2.run)

        p1.start()
        p2.start()

        pm = ProcessMonitor(p1, p2)
        pm.add_callbacks(pm.kill_processes, pm.exit)
        pm.start()

        wait_for_processes(10, p1, p2)

        if pm.is_process_alive(p1) or pm.is_process_alive(p2):
            pm.exit()
            self.fail("Processes not killed after timeout")

    def test_exit(self):
        import logging
        logger = logging.getLogger("golem.core")

        mp1, mp2 = MockProcess(), MockProcess()

        p1 = Process(target=mp1.run)
        p2 = Process(target=mp2.run)

        p1.start()
        p2.start()

        pm = ProcessMonitor(p1, p2)

        def callback():
            logger.warning("Shutting down...")

        pm.add_callbacks(callback)
        pm.start()
        pm.exit()

        wait_for_processes(10, p1, p2)

        self.assertFalse(pm.is_process_alive(p1))
        self.assertFalse(pm.is_process_alive(p2))

    def test_add_remove_callbacks(self):
        pm = ProcessMonitor()

        pm.add_callbacks(pm.exit)
        pm.remove_callbacks(pm.exit)

        assert not pm._callbacks

    def test_add_child_process(self):
        mp1, mp2 = MockProcess(), MockProcess(timeout=1)

        p1 = Process(target=mp1.run)
        p2 = Process(target=mp2.run)

        pm = ProcessMonitor(p1)
        pm.add_child_processes(p2)

        assert len(pm._child_processes) == 2

    def test_lifecycle_popen(self):

        process = subprocess.Popen(['python', '-c', 'import time; time.sleep(1)'])
        assert ProcessMonitor.is_process_alive(process)
        assert ProcessMonitor._pid(process)
        assert ProcessMonitor.is_supported(process)

        process.communicate()
        assert not ProcessMonitor.is_process_alive(process)
        assert ProcessMonitor.exit_code(process) is not None

    def test_lifecycle_multiprocessing(self):

        process = Process(target=sleep_1sec)
        assert not ProcessMonitor.is_process_alive(process)
        assert ProcessMonitor.is_supported(process)

        process.start()
        assert ProcessMonitor.is_process_alive(process)
        process.join()

        assert not ProcessMonitor.is_process_alive(process)
        assert ProcessMonitor.exit_code(process) is not None

    def test_lifecycle_none(self):

        process = None

        assert not ProcessMonitor.is_process_alive(process)
        assert not ProcessMonitor.is_supported(process)
        assert not ProcessMonitor._pid(process)
        assert ProcessMonitor.exit_code(process) is None

    def test_kill_process_popen(self):

        process = subprocess.Popen(['python', '-c', 'import time; time.sleep(1)'])
        assert ProcessMonitor.is_process_alive(process)
        ProcessMonitor.kill_process(process)
        assert not ProcessMonitor.is_process_alive(process)

    def test_kill_process_multiprocessing(self):

        process = Process(target=sleep_1sec)
        process.start()

        assert ProcessMonitor.is_process_alive(process)
        ProcessMonitor.kill_process(process)
        assert not ProcessMonitor.is_process_alive(process)

        process = Process(target=sleep_1sec)
        ProcessMonitor.kill_process(process)

    def test_exit_code(self):

        process_psutil = psutil.Popen.__new__(psutil.Popen, None)
        process_subprocess = subprocess.Popen.__new__(subprocess.Popen, None)
        process_multiprocessing = Process.__new__(Process, None)

        process_psutil.poll = Mock()
        process_subprocess.poll = Mock()
        process_multiprocessing._popen = Mock()
        process_multiprocessing._parent_pid = os.getpid()
        process_multiprocessing._name = "test"
        process_multiprocessing._daemonic = False

        process_psutil.returncode = None
        process_subprocess.returncode = None

        assert ProcessMonitor.is_process_alive(process_psutil)
        assert ProcessMonitor.is_process_alive(process_subprocess)
        with patch('multiprocessing.Process.is_alive', side_effect=lambda: False):
            assert not ProcessMonitor.is_process_alive(process_multiprocessing)

        assert ProcessMonitor.exit_code(None) is None
        assert ProcessMonitor.exit_code(process_psutil) is None
        assert ProcessMonitor.exit_code(process_subprocess) is None
        with patch('multiprocessing.Process.exitcode') as exitcode:
            exitcode.__get__ = Mock(return_value=None)
            assert ProcessMonitor.exit_code(process_multiprocessing) is None

        process_psutil.poll = Mock()
        process_psutil.returncode = 0

        process_subprocess.poll = Mock()
        process_subprocess.returncode = 0

        assert not ProcessMonitor.is_process_alive(None)
        assert not ProcessMonitor.is_process_alive(process_psutil)
        assert not ProcessMonitor.is_process_alive(process_subprocess)

        with patch('multiprocessing.Process.exitcode') as exitcode:
            exitcode.__get__ = Mock(return_value=0)
            assert not ProcessMonitor.is_process_alive(process_multiprocessing)

        assert ProcessMonitor.exit_code(process_psutil) == 0
        assert ProcessMonitor.exit_code(process_subprocess) == 0

        with patch('multiprocessing.Process.exitcode') as exitcode:
            exitcode.__get__ = Mock(return_value=0)
            assert ProcessMonitor.exit_code(process_multiprocessing) == 0
