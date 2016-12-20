import os
import time
from Queue import Queue
from threading import Thread

from golem.client import Client
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.common import config_logging
from golem.core.simpleserializer import DictSerializer
from golem.environments.environment import Environment
from golem.rpc.mapping import aliases
from golem.rpc.session import WebSocketAddress
from golem.tools.testwithreactor import TestDirFixtureWithReactor
from gui.startapp import load_environments, start_client_process, \
    start_gui_process, GUIApp
from mock import Mock, patch
from twisted.internet.defer import Deferred


def router_start(fail_on_start):
    def start(_, _reactor, callback, errback):
        if fail_on_start:
            errback(u"Router error")
        else:
            callback(Mock())
    return start


def session_connect(fail_on_start):
    def connect(instance, *args, **kwargs):
        deferred = Deferred()
        if fail_on_start:
            deferred.errback(u"Session error")
        else:
            instance.connected = True
            deferred.callback(Mock())
        return deferred
    return connect


def session_call(resolve_fn):
    def call(_, alias, *args, **kwargs):
        deferred = Deferred()
        try:
            result = resolve_fn(alias, *args, **kwargs)
        except Exception as exc:
            deferred.errback(exc)
        else:
            deferred.callback(result)
        return deferred
    return call


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
        assert len(envs) >= 2

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

        def resolve_call(alias, *args, **kwargs):
            if alias == aliases.Environment.datadir:
                return self.path
            elif alias == aliases.Environment.opts:
                return DictSerializer.dump(ClientConfigDescriptor())
            elif alias == aliases.Environment.opt_description:
                return u'test description'
            elif alias == aliases.Payments.ident:
                return u'0xdeadbeef'
            elif alias == aliases.Crypto.key_id:
                return u'0xbadfad'
            elif alias == aliases.Task.tasks_stats:
                return dict(
                    in_network=0,
                    supported=0,
                    subtasks_computed=0,
                    subtasks_with_errors=0,
                    subtasks_with_timeout=0
                )
            elif alias == aliases.Payments.balance:
                return 0, 0, 0
            elif alias == aliases.Network.peers_connected:
                return []
            elif alias == aliases.Computation.status:
                return u''
            return 1

        with patch('logging.getLogger', return_value=logger):
            with patch('golem.rpc.session.Session.connect', session_connect(session_fails)):
                with patch('golem.rpc.session.Session.call', session_call(resolve_call)):
                    try:
                        gui_app = GUIApp(rendering=True)
                        gui_app.app.execute = lambda *a, **kw: logger.error(u"Success")
                        gui_app.logic.customizer = Mock()

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
