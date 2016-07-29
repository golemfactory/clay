import os
from multiprocessing import Queue

from mock import Mock

from gnr.gnrstartapp import load_environments, start_client_process, \
    start_gui_process, GUIApp
from golem.client import Client
from golem.core.common import config_logging
from golem.environments.environment import Environment
from golem.rpc.websockets import WebSocketRPCServerFactory
from golem.tools.testwithreactor import TestDirFixtureWithReactor


class MockService(object):
    def method(self):
        return True


class TestStartAppFunc(TestDirFixtureWithReactor):

    def test_config_logging(self):
        log_name = "golem.test"
        path = os.path.join(self.path, 'subdir1', 'subdir2', log_name)
        config_logging(log_name)
        config_logging(path)

    def test_load_environments(self):
        envs = load_environments()
        for el in envs:
            assert isinstance(el, Environment)
        assert len(envs) > 2

    def test_start_client(self):
        client = Client(datadir=self.path,
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

        start_gui_process(queue, self.path,
                          gui_app=gui_app,
                          reactor=reactor)
