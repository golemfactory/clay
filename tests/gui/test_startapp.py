import os
from mock import Mock, patch
from multiprocessing import Queue

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

    @patch('logging.config.fileConfig')
    def test_config_logging(self, _):
        path = os.path.join(self.path, 'subdir1', 'subdir2', "golem.test")
        config_logging(path)
        assert os.path.exists(os.path.dirname(path))

    def test_load_environments(self):
        envs = load_environments()
        for el in envs:
            assert isinstance(el, Environment)
        assert len(envs) > 2

    @patch('logging.config.fileConfig')
    def test_start_client(self, *_):
        client = None

        try:
            client = Client(datadir=self.path,
                            transaction_system=False,
                            connect_to_known_hosts=False,
                            use_docker_machine_manager=False,
                            use_monitor=False)

            start_client_process(queue=Mock(),
                                 client=client,
                                 start_ranking=False)
        except Exception as exc:
            self.fail("Cannot start client process: {}".format(exc))
        finally:
            if client:
                client.quit()

    @patch('logging.config.fileConfig')
    def test_start_gui(self, *_):
        queue = Queue()

        rpc_server = WebSocketRPCServerFactory()
        rpc_server.local_host = '127.0.0.1'

        mock_service_info = rpc_server.add_service(MockService())
        queue.put(mock_service_info)

        gui_app = None

        try:
            gui_app = GUIApp(rendering=True)
            gui_app.listen = Mock()
            reactor = self._get_reactor()

            start_gui_process(queue, self.path,
                              gui_app=gui_app,
                              reactor=reactor)
        except Exception as exc:
            self.fail("Cannot start gui process: {}".format(exc))
        finally:
            if gui_app and gui_app.app and gui_app.app.app:
                gui_app.app.app.exit(0)
                gui_app.app.app.deleteLater()
