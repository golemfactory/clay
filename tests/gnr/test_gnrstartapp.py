import time
import unittest
from multiprocessing import Process, Queue

from mock import Mock

from gnr.gnrstartapp import config_logging, load_environments, start_client_process, \
    ProcessMonitor, start_gui_process, GUIApp
from golem.client import create_client
from golem.environments.environment import Environment
from golem.rpc.websockets import WebSocketRPCServerFactory
from golem.tools.testwithreactor import TestDirFixtureWithReactor


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


class MockService(object):
    def method(self):
        return True


def wait_for_processes(timeout=10, *processes):
    started = time.time()
    timeout = max(timeout, 5)
    while time.time() - started < timeout:
        all_stopped = True

        for process in processes:
            if process.is_alive():
                all_stopped = False
                break

        if all_stopped:
            break
        else:
            time.sleep(0.5)


class TestProcessMonitor(unittest.TestCase):

    def test_monitor(self):

        def run_exit():
            pass

        mp = MockProcess()
        p1 = Process(target=run_exit)
        p2 = Process(target=mp.run)

        p1.start()
        p2.start()

        pm = ProcessMonitor(p1, p2)
        pm.stop_reactor = False
        pm.start()

        wait_for_processes(10, p1, p2)

        assert not p1.is_alive()
        assert not p2.is_alive()

    def test_monitor_2(self):
        mp1, mp2 = MockProcess(), MockProcess(timeout=0)

        p1 = Process(target=mp1.run)
        p2 = Process(target=mp2.run)

        p1.start()
        p2.start()

        pm = ProcessMonitor(p1, p2)
        pm.stop_reactor = False
        pm.start()

        wait_for_processes(10, p1, p2)

        if p1.is_alive() or p2.is_alive():
            pm.exit()
            self.fail("Processes not killed after timeout")

    def test_exit(self):

        mp1, mp2 = MockProcess(), MockProcess()
        p1 = Process(target=mp1.run)
        p2 = Process(target=mp2.run)

        p1.start()
        p2.start()

        pm = ProcessMonitor(p1, p2)
        pm.stop_reactor = False
        pm.start()
        pm.exit()

        wait_for_processes(10, p1, p2)

        assert not p1.is_alive()
        assert not p2.is_alive()


def mock_start_client(*args, **kwargs):
    return create_client(*args, **kwargs)


class TestStartAppFunc(TestDirFixtureWithReactor):

    def test_config_logging(self):
        config_logging()

    def test_load_environments(self):
        envs = load_environments()
        for el in envs:
            assert isinstance(el, Environment)
        assert len(envs) > 2

    def test_start_client(self):
        client = create_client(datadir=self.path,
                               transaction_system=False,
                               connect_to_known_hosts=False)

        try:
            start_client_process(queue=Mock(),
                                 client=client,
                                 start_ranking=False)
        except Exception as exc:
            self.fail("Failed to start client process: {}".format(exc))
        finally:
            client.quit()

    def test_start_gui(self):
        queue = Queue()
        rpc_server = WebSocketRPCServerFactory()
        rpc_server.local_host = '127.0.0.1'

        mock_service_info = rpc_server.add_service(MockService())
        queue.put(mock_service_info)

        gui_app = GUIApp(rendering=True)
        gui_app.listen = Mock()
        reactor = self._get_reactor()

        start_gui_process(queue,
                          gui_app=gui_app,
                          reactor=reactor)
