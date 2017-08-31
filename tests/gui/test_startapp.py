import sys
import time
from queue import Queue
from threading import Thread

from mock import Mock, patch, ANY
from twisted.internet.defer import Deferred

from golem.client import Client
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.simpleserializer import DictSerializer
from golem.environments.environment import Environment
from golem.rpc.mapping import aliases
from golem.rpc.session import WebSocketAddress
from golem.tools.ci import ci_patch
from golem.tools.testwithreactor import TestDirFixtureWithReactor
from gui.startapp import load_environments, start_client, stop_reactor, start_app
from twisted.python import failure


def router_start(fail_on_start):
    def start(_, _reactor, callback, errback):
        if fail_on_start:
            errback("Router error")
        else:
            callback(Mock())

    return start


def session_connect(fail_on_start):
    def connect(instance, *args, **kwargs):
        deferred = Deferred()
        if fail_on_start:
            deferred.errback(failure.Failure(ValueError("Session error")))
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


@patch('twisted.internet.iocpreactor', create=True)
class TestStartAppFunc(TestDirFixtureWithReactor):

    def _start_client(self, router_fails=False, session_fails=False, expected_result=None):

        queue = Queue()

        @patch('devp2p.app.BaseApp.start')
        @patch('devp2p.app.BaseApp.stop')
        @patch('gui.startapp.start_gui')
        @patch('golem.client.Client.start', side_effect=lambda *_: queue.put("Success"))
        @patch('golem.client.Client.sync')
        @patch('gui.startapp.start_error', side_effect=lambda err: queue.put(err))
        @patch('golem.rpc.router.CrossbarRouter.start', router_start(router_fails))
        @patch('golem.rpc.session.Session.connect', session_connect(session_fails))
        def inner(*mocks):
            client = None
            try:
                client = Client(datadir=self.path,
                                transaction_system=False,
                                connect_to_known_hosts=False,
                                use_docker_machine_manager=False,
                                use_monitor=False)

                start_client(start_ranking=False, client=client,
                             reactor=self._get_reactor())

                message = queue.get(True, 10)
                if isinstance(message, failure.Failure):
                    assert message.getErrorMessage().find(expected_result) != -1
                else:
                    assert str(message).find(expected_result) != -1
            except Exception as exc:
                self.fail("Cannot start client process: {}".format(exc))
            finally:
                if client:
                    client.quit()

        return inner()

    def _start_gui(self, session_fails=False, expected_result=None):

        address = WebSocketAddress('127.0.0.1', 50000, realm='golem')
        logger = Mock()

        def resolve_call(alias, *args, **kwargs):
            if alias == aliases.Environment.datadir:
                return self.path
            elif alias == aliases.Environment.opts:
                return DictSerializer.dump(ClientConfigDescriptor())
            elif alias == aliases.Environment.opt_description:
                return 'test description'
            elif alias == aliases.Payments.ident:
                return '0xdeadbeef'
            elif alias == aliases.Crypto.key_id:
                return '0xbadfad'
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
                return ''
            return 1

        with patch('logging.getLogger', return_value=logger), \
             patch('gui.startgui.start_error', side_effect=lambda err: logger.error(err)), \
             patch('gui.startgui.GUIApp.start', side_effect=lambda *a, **kw: logger.error("Success")), \
             patch('gui.startgui.install_qt5_reactor', side_effect=self._get_reactor), \
             patch('golem.rpc.session.Session.connect', session_connect(session_fails)), \
             patch('golem.rpc.session.Session.call', session_call(resolve_call)):

            try:

                from gui.startgui import GUIApp, start_gui

                gui_app = GUIApp(rendering=True)
                gui_app.gui.execute = lambda *a, **kw: logger.error("Success")
                gui_app.logic.customizer = Mock()

                thread = Thread(target=lambda: start_gui(address, gui_app))
                thread.daemon = True
                thread.start()

                deadline = time.time() + 10
                while True:

                    if logger.error.called:
                        if not logger.error.call_args:
                            raise Exception("Invalid result: {}".format(logger.error.call_args))

                        message = logger.error.call_args[0][0]
                        if isinstance(message, failure.Failure):
                            assert message.getErrorMessage().find(
                                expected_result) != -1
                        else:
                            assert message.find(expected_result) != -1
                        break

                    elif time.time() > deadline:
                        raise Exception("Test timed out")
                    else:
                        time.sleep(0.1)

            except Exception as exc:
                self.fail("Cannot start gui process: {}".format(exc))

    @patch('logging.config.fileConfig')
    @ci_patch('golem.docker.manager.DockerManager.check_environment',
              return_value=True)
    @ci_patch('golem.docker.environment.DockerEnvironment.check_docker_images',
              return_value=True)
    def test_start_client_success(self, *_):
        self._start_client(expected_result="Success")

    @patch('logging.config.fileConfig')
    @ci_patch('golem.docker.manager.DockerManager.check_environment',
              return_value=True)
    @ci_patch('golem.docker.environment.DockerEnvironment.check_docker_images',
              return_value=True)
    def test_start_client_router_failure(self, *_):
        self._start_client(router_fails=True,
                           expected_result="Router error")

    @patch('logging.config.fileConfig')
    @ci_patch('golem.docker.manager.DockerManager.check_environment',
              return_value=True)
    @ci_patch('golem.docker.environment.DockerEnvironment.check_docker_images',
              return_value=True)
    def test_start_client_session_failure(self, *_):
        self._start_client(session_fails=True,
                           expected_result="Session error")

    @patch('logging.config.fileConfig')
    @ci_patch('golem.docker.manager.DockerManager.check_environment',
              return_value=True)
    @ci_patch('golem.docker.environment.DockerEnvironment.check_docker_images',
              return_value=True)
    def test_start_gui_success(self, *_):
        self._start_gui(expected_result="Success")

    @patch('logging.config.fileConfig')
    @patch('gui.startgui.config_logging')
    @ci_patch('golem.docker.manager.DockerManager.check_environment',
              return_value=True)
    @ci_patch('golem.docker.environment.DockerEnvironment.check_docker_images',
              return_value=True)
    def test_start_gui_failure(self, *_):
        self._start_gui(session_fails=True,
                        expected_result="Session error")

    @patch('twisted.internet.reactor')
    def test_stop_reactor(self, reactor, *_):
        reactor.running = False
        stop_reactor()
        assert not reactor.stop.called

        reactor.running = True
        stop_reactor()
        assert reactor.stop.called

    @patch('golem.docker.manager.DockerManager.command')
    @patch('gui.startapp.start_client')
    def test_start_app(self, _start_client, *_):
        start_app(datadir=self.tempdir)
        _start_client.assert_called_with(False, self.tempdir, False,
                                         use_monitor=True, geth_port=None)

    def test_load_environments(self, *_):
        envs = load_environments()
        for el in envs:
            assert isinstance(el, Environment)
        assert len(envs) >= 2

    def test_start_gui_subprocess(self, *_):

        from gui.startapp import start_gui as _start_gui

        rpc_address = WebSocketAddress('127.0.0.1', 12345, 'golem')
        address_str = '{}:{}'.format(rpc_address.host, rpc_address.port)

        with patch('gui.startgui.install_qt5_reactor', side_effect=self._get_reactor):

            expected_kwargs = dict(
                startupinfo=ANY,
                stdout=-1,
                stderr=-1,
                stdin=ANY
            )

            with patch('subprocess.Popen') as popen:
                _start_gui(rpc_address)
                popen.assert_called_with([sys.executable, ANY,
                                          '--qt', '-r', address_str],
                                         **expected_kwargs)

            with patch('subprocess.Popen') as popen, \
                 patch.object(sys, 'executable', 'python_binary'):

                _start_gui(rpc_address)
                popen.assert_called_with(['python_binary', ANY,
                                          '--qt', '-r', address_str],
                                         **expected_kwargs)

            with patch('subprocess.Popen') as popen, \
                 patch.object(sys, 'frozen', True, create=True):

                _start_gui(rpc_address)
                popen.assert_called_with([sys.executable,
                                          '--qt', '-r', address_str],
                                         **expected_kwargs)
