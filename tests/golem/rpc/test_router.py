# The code below is organised in classes, each class running one test only.
# This is because closing reactor and router and running them again ends with
# a timeout error during session.connect(). This proved to be challenging
# to debug, so this not-so-pretty solution of running tests separately
# was used.
import time
from threading import Thread
from unittest import mock

from autobahn.twisted import util
from autobahn.wamp import ApplicationError
from twisted.internet.defer import inlineCallbacks
from twisted.internet.defer import setDebugging

from golem.rpc.cert import CrossbarAuthManager
from golem.rpc.common import CROSSBAR_DIR, CROSSBAR_PORT
from golem.rpc.mapping.rpcmethodnames import DOCKER_URI
from golem.rpc.router import CrossbarRouter
from golem.rpc.session import Session, object_method_map, Client, Publisher
from golem.tools.testwithreactor import TestDirFixtureWithReactor


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


class _TestRouter(TestDirFixtureWithReactor):
    TIMEOUT = 20

    # pylint: disable=too-many-instance-attributes
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

            self.generate_secrets = True
            self.crsb_frontend = None
            self.crsb_frontend_secret = None
            self.crsb_backend = None
            self.crsb_backend_secret = None
            self.subscribe = False

            self.cmanager = None
            self.method = None

        def add_errors(self, *errors):
            print('Errors: {}'.format(errors))
            if errors:
                self.errors += errors
            else:
                self.errors += ['Unknown error']

    def setUp(self):
        super().setUp()
        self.state = _TestRouter.State(self.reactor_thread.reactor)

    def _start_backend_session(self, *_):

        user = self.state.crsb_backend
        secret = self.state.crsb_backend_secret

        s = self.Session(  # pylint: disable=no-member
            self.state.router.address,
            methods=object_method_map(
                self.state.backend,
                MockService.methods
            ),
            crsb_user=user,
            crsb_user_secret=secret
        )
        self.state.backend_session = s

        self.state.backend_session = s

        self.state.backend_deferred = self.state.backend_session.connect()
        self.state.backend_deferred.addCallbacks(
            self._backend_session_started, self.state.add_errors
        )

    def _backend_session_started(self, *_):
        user = self.state.crsb_frontend
        secret = self.state.crsb_frontend_secret if user else None
        events = object_method_map(
            self.state.frontend,
            MockService.events
        ) if self.state.subscribe else None

        s = self.Session(  # pylint: disable=no-member
            self.state.router.address,
            events=events,
            crsb_user=user,
            crsb_user_secret=secret
        )
        self.state.frontend_session = s

        self.state.frontend_session = s

        self.state.frontend_deferred = self.state.frontend_session.connect()
        self.state.frontend_deferred.addCallbacks(
            self._frontend_session_started, self.state.add_errors
        )

    def _wait_for_thread(self, expect_error=False):
        deadline = time.time() + self.TIMEOUT

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
        self.reactor_thread.reactor.stop()

    def _run_test(self, expect_error, *args, **kwargs):
        thread = Thread(target=self._start_router, args=args, kwargs=kwargs)
        thread.daemon = True
        thread.run()

        self._wait_for_thread(expect_error=expect_error)

    # pylint: disable=unused-argument
    def _start_router(self, *args, **kwargs):
        raise NotImplementedError()

    def _frontend_session_started(self, *_):
        raise NotImplementedError()


class TestRPCNoAuth(_TestRouter):

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

    def test_rpc_no_auth(self):
        self.state.subscribe = True
        self._run_test(False)

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

    @inlineCallbacks
    def _frontend_session_started(self, *_):
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

    # pylint: disable=arguments-differ
    def _start_router(self):
        # pylint: disable=no-member
        self.state.router = CrossbarRouter(
            datadir=self.path,
            ssl=False,
            generate_secrets=self.state.generate_secrets
        )
        # set a new role for admin
        self.state.router.config["workers"][0]["transports"][0]["auth"]["anonymous"] = {  # noqa pylint: disable=line-too-long
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
        # pylint: disable=attribute-defined-outside-init
        self.Session = type("Session_no_auth",
                            Session.__bases__,
                            dict(Session.__dict__))
        del self.Session.onChallenge
        del self.Session.onConnect

        deferred = self.state.router.start(self.state.reactor)
        deferred.addCallbacks(self._start_backend_session,
                              self.state.add_errors)


class _TestRPCAuth(_TestRouter):
    DOCKER = CrossbarAuthManager.Users.docker
    GOLEMAPP = CrossbarAuthManager.Users.golemapp
    GOLEMCLI = CrossbarAuthManager.Users.golemcli
    DOCKER_METHOD = "docker_echo"
    NON_DOCKER_METHOD = "non_docker_echo"
    TIMEOUT = 10

    @mock.patch("golem.rpc.cert.CrossbarAuthManager.get_secret",
                lambda *_: "secret")
    # pylint: disable=arguments-differ
    def _start_router(self, *args, port=CROSSBAR_PORT, path=None, **kwargs):
        self.state.subscribe = False
        path = path if path else self.path
        self.state.router = CrossbarRouter(datadir=path,
                                           ssl=False,
                                           generate_secrets=True,
                                           port=port)
        # pylint: disable=attribute-defined-outside-init
        self.Session = Session
        deferred = self.state.router.start(self.state.reactor)

        deferred.addCallbacks(  # pylint: disable=no-member
            self._start_backend_session,
            self.state.add_errors
        )

    @inlineCallbacks
    def _frontend_session_started(self, *_):
        client = Client(self.state.frontend_session, MockService.methods)
        result = yield getattr(client, self.state.method)("something")
        assert result == "something"
        yield self.state.router.stop()
        self.state.done = True

    def _test_rpc_auth_method_access(self, frontend, backend, method, error):
        self.state = _TestRouter.State(self.reactor_thread.reactor)
        self.state.crsb_frontend = frontend
        self.state.crsb_backend = backend
        self.state.crsb_frontend_secret = "secret"
        self.state.crsb_backend_secret = "secret"
        self.state.method = method
        self._run_test(error, port=CROSSBAR_PORT, path=self.path)


class TestRPCAuthDockerGolemappDockermethod(_TestRPCAuth):
    def test_rpc_auth_method_access(self):
        self._test_rpc_auth_method_access(
            self.DOCKER, self.GOLEMAPP, self.DOCKER_METHOD, False
        )


class TestRPCAuthCliGolemappNondockermethod(_TestRPCAuth):
    def test_rpc_auth_method_access(self):
        self._test_rpc_auth_method_access(
            self.GOLEMCLI, self.GOLEMAPP, self.NON_DOCKER_METHOD, False
        )


class TestRPCAuthCliGolemappDockermethod(_TestRPCAuth):
    def test_rpc_auth_method_access(self):
        self._test_rpc_auth_method_access(
            self.GOLEMCLI, self.GOLEMAPP, self.DOCKER_METHOD, False
        )


class TestRPCAuthDockerGolemappNondockermethod(_TestRPCAuth):
    def test_rpc_auth_method_access(self):
        self._test_rpc_auth_method_access(
            self.DOCKER, self.GOLEMAPP, self.NON_DOCKER_METHOD, True
        )


class TestRPCAuthCliDockerDockermethod(_TestRPCAuth):
    def test_rpc_auth_method_access(self):
        self._test_rpc_auth_method_access(
            self.GOLEMCLI, self.DOCKER, self.DOCKER_METHOD, True
        )


class _TestRPCAuthWrongSecret(_TestRPCAuth):
    def _prepare_wrong_secret(self):
        self.state.router = CrossbarRouter(datadir=self.path,
                                           ssl=False,
                                           generate_secrets=True)
        self.state.cmanager = CrossbarAuthManager(self.path)
        self.state.crsb_frontend = self.GOLEMCLI
        self.state.crsb_backend = self.GOLEMAPP


# pylint: disable=too-many-ancestors
class TestRPCAuthWrongBackendSecret(_TestRPCAuthWrongSecret):
    def test_rpc_auth_wrong_backend_secret(self):
        self._prepare_wrong_secret()
        self.state.crsb_frontend_secret = self.state.cmanager.get_secret(
            self.state.crsb_frontend
        )
        self.state.crsb_backend_secret = "wrong_secret"
        self._run_test(True, port=CROSSBAR_PORT, path=self.path)


# pylint: disable=too-many-ancestors
class TestRPCAuthWrongFrontendSecret(_TestRPCAuthWrongSecret):
    def test_rpc_auth_wrong_backend_secret(self):
        self._prepare_wrong_secret()
        self.state.crsb_frontend_secret = self.state.cmanager.get_secret(
            self.state.crsb_frontend
        )
        self.state.crsb_backend_secret = "wrong_secret"
        self._run_test(True, port=CROSSBAR_PORT, path=self.path)
