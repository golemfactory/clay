import json
import os
import time
from threading import Thread
from unittest import mock

import pytest
from autobahn.twisted import util
from autobahn.wamp import ApplicationError

from golem.rpc.cert import CertificateManager
from golem.rpc.common import CROSSBAR_DIR
from golem.rpc.mapping.rpcmethodnames import DOCKER_URI
from golem.rpc.router import CrossbarRouter
from golem.rpc.session import Session, object_method_map, Client, Publisher
from golem.tools.testwithreactor import TestDirFixtureWithReactor, replace_reactor, MockReactorThread, uninstall_reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.defer import setDebugging

setDebugging(True)


class MockService(object):
    methods = dict(
        multiply='mock.multiply',
        divide='mock.divide',
        ping='mock.ping',
        exception='mock.exception',
        docker_echo=f'{DOCKER_URI}.echo',
        non_docker_echo='mock.echo'
    )

    events = dict(
        on_hello='mock.event.hello'
    )

    def __init__(self):
        self.n_hello_received = 0

    def multiply(self, arg1, arg2):
        return arg1 * arg2

    def divide(self, number, divisor=2):
        return number / divisor

    def ping(self):
        return 'pong'

    def docker_echo(self, arg):
        return arg

    def non_docker_echo(self, arg):
        return arg

    def exception(self):
        n = 2
        if n % 2 == 0:
            raise AttributeError("Mock error raised")
        return 2

    def on_hello(self):
        self.n_hello_received += 1


class TestRouter(TestDirFixtureWithReactor):
    TIMEOUT = 20

    class State(object):

        def __init__(self, reactor):
            self.done = False
            self.errors = []

            self.reactor = reactor
            self.router = None

            self.backend = MockService()
            self.backend_session = None
            self.backend_deferred = None
            self.frontend = MockService()
            self.frontend_session = None
            self.frontend_deferred = None

        def add_errors(self, *errors):
            print('Errors: {}'.format(errors))
            if errors:
                self.errors += errors
            else:
                self.errors += ['Unknown error']

    def setUp(self):
        # super().tearDownClass()
        # super().setUpClass()
        super().setUp()
        self.state = TestRouter.State(self.reactor_thread.reactor)

    def test_init(self):
        from os.path import join, exists

        crossbar_dir = join(self.path, 'definitely_not_exists')
        router = CrossbarRouter(datadir=crossbar_dir,
                                generate_secrets=True)
        assert exists(crossbar_dir)
        self.assertIsInstance(router, CrossbarRouter)
        self.assertEqual(router.working_dir, join(crossbar_dir, 'crossbar'))

        router = CrossbarRouter(datadir=join(self.path, "crozzbar"),
                                generate_secrets=True)
        self.assertEqual(router.working_dir, join(self.path,
                                                  'crozzbar',
                                                  CROSSBAR_DIR))
        self.assertIsNone(router.node)
        self.assertIsNone(router.pubkey)

        tmp_file = join(self.path, 'tmp_file')
        with open(tmp_file, 'w') as f:
            f.write('tmp data')

        with self.assertRaises(IOError):
            CrossbarRouter(datadir=tmp_file)

    def _start_router_no_auth(self):
        # pylint: disable=no-member
        self.state.router = CrossbarRouter(datadir=self.path,
                                           ssl=False,
                                           generate_secrets=True)
        # set a new role for admin
        self.state.router.config["workers"][0]["transports"][0]["auth"]["anonymous"] = {
            "type": "static",
            "role": "golem_admin"
        }

        self.state.router.config["workers"][0]["realms"][0]["roles"].append(
            {
                "name": 'anonymous',
                "permissions": [{
                    "uri": '*',
                    "allow": {
                        "call": True,
                        "register": True,
                        "publish": True,
                        "subscribe": True
                    }
                }]
            }
        )

        # These methods are for auth, which is not used in this test
        # and with them, crossbar doesn't work
        self.Session = type("Session_no_auth",
                            Session.__bases__,
                            dict(Session.__dict__))
        del self.Session.onChallenge
        del self.Session.onConnect

        deferred = self.state.router.start(self.state.reactor)
        deferred.addCallbacks(self._start_backend_session,
                              self.state.add_errors)

    def _start_backend_session(self, *_):
        print("start_backend_session1")

        user = self.state.crsb_backend if hasattr(self.state, "crsb_backend") else None
        secret = self.state.crsb_backend_secret if user else None
        print("start_backend_session2")

        s = self.Session(
            self.state.router.address,
            methods=object_method_map(
                self.state.backend,
                MockService.methods
            ),
            crsb_user=user,
            crsb_user_secret=secret
        )
        print("start_backend_session3")
        self.state.backend_session = s

        self.state.backend_deferred = self.state.backend_session.connect()
        self.state.backend_deferred.addCallbacks(
            self._backend_session_started, self.state.add_errors
        )
        print("start_backend_session4")

    def _backend_session_started(self, *_):
        print("_backend_session_started1")
        user = self.state.crsb_frontend if hasattr(self.state, "crsb_frontend") else None
        secret = self.state.crsb_frontend_secret if user else None
        events = object_method_map(
                self.state.frontend,
                MockService.events
            ) if self.state.subscribe else None

        s = self.Session(
            self.state.router.address,
            events=events,
            crsb_user=user,
            crsb_user_secret=secret
        )
        print("_backend_session_started2")
        self.state.frontend_session = s

        self.state.frontend_deferred = self.state.frontend_session.connect()
        self.state.frontend_deferred.addCallbacks(
            self._frontend_session_started_method, self.state.add_errors
        )
        print("_backend_session_started3")

    @inlineCallbacks
    def _frontend_session_started(self, *_):
        print("_frontend_session_started")
        client = Client(self.state.frontend_session, MockService.methods)
        publisher = Publisher(self.state.backend_session)

        multiply_result = yield client.multiply(2, 3)
        assert multiply_result == 6

        divide_result = yield client.divide(4)
        assert divide_result == 2

        divide_result = yield client.divide(8, 4)
        assert divide_result == 2

        assert self.state.frontend.n_hello_received == 0
        yield publisher.publish('mock.event.hello')
        yield util.sleep(0.5)
        assert self.state.frontend.n_hello_received > 0
        with self.assertRaises(ApplicationError):
            yield client.exception()

        ping_result = yield client.ping()
        assert ping_result == 'pong'
        yield self.state.router.stop()
        self.state.done = True

    def _wait_for_thread(self, expect_error=False):
        deadline = time.time() + self.TIMEOUT
        # self.state.done = False
        # self.state.errors = []

        while True:
            time.sleep(0.5)
            if time.time() > deadline:
                self.state.errors.append(Exception("Test timed out"))
            if self.state.errors or self.state.done:
                break

        if self.state.frontend_session:
            self.state.frontend_session.disconnect()

        if self.state.backend_session:
            self.state.backend_session.disconnect()

        time.sleep(0.5)

        if self.state.errors and not expect_error:
            raise Exception(*self.state.errors)

        if expect_error and not self.state.errors:
            raise Exception("Expected error")

    def test_rpc_no_auth(self):
        self._frontend_session_started_method = self._frontend_session_started
        self.state.subscribe = True

        thread = Thread(target=self._start_router_no_auth)
        thread.daemon = True
        thread.start()

        self._wait_for_thread(thread, expect_error=False)

    @mock.patch("golem.rpc.cert.CertificateManager.get_secret", lambda *_: "secret")
    def _start_router_auth(self):
        self.state.router = CrossbarRouter(datadir=self.path,
                                           ssl=False,
                                           generate_secrets=False)

        self.Session = Session
        deferred = self.state.router.start(self.state.reactor)
        deferred.addCallbacks(self._start_backend_session,
                              self.state.add_errors)

    def _start_test_auth(self, expect_error):
        self._frontend_session_started_method = self._frontend_session_started_auth
        self.state.subscribe = False
        print("STARTING")
        thread = Thread(target=self._start_router_auth)
        thread.daemon = True
        thread.start()

        self._wait_for_thread(thread, expect_error=expect_error)
        print("EXITING")

    @inlineCallbacks
    def _frontend_session_started_auth(self, *_):
        print("_frontend_session_started_auth1")
        client = Client(self.state.frontend_session, MockService.methods)
        print("_frontend_session_started_auth2")
        result = yield getattr(client, self.state.method)("something")
        assert result == "something"
        print("_frontend_session_started_auth3")
        yield self.state.router.stop()
        self.state.done = True
        print("_frontend_session_started_auth4")

    # @pytest.mark.slow
    def test_rpc_auth_method_access(self):
        tm = self.TIMEOUT
        self.TIMEOUT = 10

        docker = CertificateManager.Crossbar_users.docker
        golemapp = CertificateManager.Crossbar_users.golemapp
        golemcli = CertificateManager.Crossbar_users.golemcli
        docker_method = "docker_echo"
        non_docker_method = "non_docker_echo"
        testing_set = [
            # {
            #     "frontend": docker,
            #     "backend": golemapp,
            #     "method": docker_method,
            #     "error": False,
            # },
            # {
            #     "frontend": docker,
            #     "backend": golemapp,
            #     "method": non_docker_method,
            #     "error": True,
            # },
            # {
            #     "frontend": golemcli,
            #     "backend": docker,
            #     "method": docker_method,
            #     "error": True,
            # },
            {
                "frontend": golemcli,
                "backend": golemapp,
                "method": non_docker_method,
                "error": False,
            },
            # {
            #     "frontend": golemcli,
            #     "backend": golemapp,
            #     "method": docker_method,
            #     "error": False,
            # }
        ]

        for elem in testing_set:
            # if self.reactor_thread and self.reactor_thread.isAlive():
            #     self.reactor_thread.stop()
            #     # uninstall_reactor()
            # try:
            #     _reactor, self.prev_reactor = replace_reactor()
            #     _reactor.installed = True
            #     self.reactor_thread = MockReactorThread(_reactor)
            #     self.reactor_thread.start()
            # except Exception as e:
            #     print("Reactor exception: ", e)

            print(elem)

            self.state.crsb_frontend = elem["frontend"]
            self.state.crsb_backend = elem["backend"]
            self.state.crsb_frontend_secret = "secret"
            self.state.crsb_backend_secret = "secret"
            self.state.method = elem["method"]
            self._start_test_auth(elem["error"])


        self.TIMEOUT = tm

    def test_rpc_auth_wrong_secret(self):
        tm = self.TIMEOUT
        self.TIMEOUT = 5

        self.state.router = CrossbarRouter(datadir=self.path,
                                           ssl=False,
                                           generate_secrets=True)
        cmanager = CertificateManager(os.path.join(self.path, CROSSBAR_DIR))

        golemcli = cmanager.Crossbar_users.golemcli
        golemapp = cmanager.Crossbar_users.golemapp

        self.state.crsb_frontend = golemcli
        self.state.crsb_backend = golemapp
        self.state.crsb_frontend_secret = "wrong_secret"
        self.state.crsb_backend_secret = cmanager.get_secret(self.state.crsb_backend)
        self._start_test_auth(True)

        self.state.crsb_frontend = golemcli
        self.state.crsb_backend = golemapp
        self.state.crsb_frontend_secret = cmanager.get_secret(self.state.crsb_frontend)
        self.state.crsb_backend_secret = "wrong_secret"
        self._start_test_auth(True)

        self.TIMEOUT = tm
