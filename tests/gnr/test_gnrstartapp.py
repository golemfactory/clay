import os
from Queue import Queue
from threading import Thread

import time
from gnr.gnrstartapp import load_environments, start_client_process, \
    start_gui_process, GUIApp
from golem.client import Client
from golem.core.common import config_logging
from golem.environments.environment import Environment
from golem.rpc.session import WebSocketAddress
from golem.tools.testwithreactor import TestDirFixtureWithReactor
from mock import Mock, patch
from twisted.internet.defer import Deferred


def router_start(fail_on_start):
    def start(_self, _reactor, callback, errback):
        if fail_on_start:
            errback(u"Router error")
        else:
            callback(Mock())
    return start


def session_connect(fail_on_start):
    def connect(*args, **kwargs):
        deferred = Deferred()
        if fail_on_start:
            deferred.errback(u"Session error")
        else:
            deferred.callback(Mock())
        return deferred
    return connect


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

    def _start_client(self, router_fails=False, session_fails=False, expected_result=None):

        client = None
        queue = Queue()

        with patch('golem.rpc.router.CrossbarRouter.start', router_start(router_fails)):
            with patch('golem.rpc.session.Session.connect', session_connect(session_fails)):

                try:
                    client = Client(datadir=self.path,
                                    transaction_system=False,
                                    connect_to_known_hosts=False,
                                    use_docker_machine_manager=False,
                                    use_monitor=False)

                    client.start = lambda *_: queue.put(u"Success")

                    thread = Thread(target=lambda: start_client_process(queue=queue,
                                                                        client=client,
                                                                        start_ranking=False))
                    thread.daemon = True
                    thread.start()

                    message = queue.get(True, 10)
                    assert unicode(message).find(expected_result) != -1

                except Exception as exc:
                    import traceback
                    traceback.print_exc()
                    self.fail(u"Cannot start client process: {}".format(exc))
                finally:
                    if client:
                        client.quit()

    def _start_gui(self, session_fails=False, expected_result=None):

        gui_app = None
        address = WebSocketAddress('127.0.0.1', 50000, realm=u'golem')

        queue = Queue()
        queue.put(address)

        logger = Mock()

        with patch('logging.getLogger', return_value=logger):
            with patch('golem.rpc.session.Session.connect', session_connect(session_fails)):
                try:
                    gui_app = GUIApp(rendering=True)
                    gui_app.start = lambda *_: logger.error(u"Success")

                    thread = Thread(target=lambda: start_gui_process(queue,
                                                                     datadir=self.path,
                                                                     gui_app=gui_app,
                                                                     reactor=self._get_reactor()))
                    thread.daemon = True
                    thread.start()

                    started = time.time()
                    while True:

                        if logger.error.called:
                            if not logger.error.call_args:
                                raise Exception(u"Invalid result: {}".format(logger.error.call_args))

                            message = logger.error.call_args[0][0]
                            assert unicode(message).find(expected_result) != -1
                            break

                        elif time.time() > started + 10:
                            raise Exception(u"Test timed out")
                        else:
                            time.sleep(0.1)

                except Exception as exc:
                    self.fail(u"Cannot start gui process: {}".format(exc))
                finally:
                    if gui_app and gui_app.app and gui_app.app.app:
                        gui_app.app.app.exit(0)
                        gui_app.app.app.deleteLater()

    @patch('logging.config.fileConfig')
    def test_start_client_success(self, *_):
        self._start_client(expected_result=u"Success")

    @patch('logging.config.fileConfig')
    def test_start_client_router_failure(self, *_):
        self._start_client(router_fails=True,
                           expected_result=u"Router error")

    @patch('logging.config.fileConfig')
    def test_start_client_session_failure(self, *_):
        self._start_client(session_fails=True,
                           expected_result=u"Session error")

    @patch('logging.config.fileConfig')
    def test_start_gui_success(self, *_):
        self._start_gui(expected_result=u"Success")

    @patch('logging.config.fileConfig')
    def test_start_gui_failure(self, *_):
        self._start_gui(session_fails=True,
                        expected_result=u"Session error")
