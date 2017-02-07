import time
from multiprocessing import Process

import subprocess

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

    def test_process_timeout(self):
        mp1, mp2 = MockProcess(), MockProcess(timeout=1)

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
        mp1, mp2 = MockProcess(), MockProcess()
        p1 = Process(target=mp1.run)
        p2 = Process(target=mp2.run)

        p1.start()
        p2.start()

        pm = ProcessMonitor(p1, p2)
        pm.add_callbacks(pm.kill_processes)
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
        assert ProcessMonitor._exit_code(process) is not None

    def test_lifecycle_multiprocessing(self):

        process = Process(target=lambda: time.sleep(1))
        assert not ProcessMonitor.is_process_alive(process)
        assert ProcessMonitor.is_supported(process)

        process.start()
        assert ProcessMonitor.is_process_alive(process)
        process.join()

        assert not ProcessMonitor.is_process_alive(process)
        assert ProcessMonitor._exit_code(process) is not None

    def test_lifecycle_none(self):

        process = None

        assert not ProcessMonitor.is_process_alive(process)
        assert not ProcessMonitor.is_supported(process)
        assert not ProcessMonitor._pid(process)
        assert ProcessMonitor._exit_code(process) is None

    def test_kill_process_popen(self):

        process = subprocess.Popen(['python', '-c', 'import time; time.sleep(1)'])
        assert ProcessMonitor.is_process_alive(process)
        ProcessMonitor.kill_process(process)
        assert not ProcessMonitor.is_process_alive(process)

    def test_kill_process_multiprocessing(self):

        process = Process(target=lambda: time.sleep(1))
        process.start()

        assert ProcessMonitor.is_process_alive(process)
        ProcessMonitor.kill_process(process)
        assert not ProcessMonitor.is_process_alive(process)

        process = Process(target=lambda: time.sleep(1))
        ProcessMonitor.kill_process(process)
