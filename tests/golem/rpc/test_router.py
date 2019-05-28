# pylint: disable=protected-access
# The code below is organised in classes, each class running one test only.
# This is because closing reactor and router and running them again ends with
# a timeout error during session.connect(). This proved to be challenging
# to debug, so this not-so-pretty solution of running tests separately
# was used.


import os
import pprint
import time
from multiprocessing import Process
import typing
from unittest import mock, skip

from autobahn.twisted import util
from autobahn.wamp import ApplicationError
import psutil
from twisted.internet.defer import inlineCallbacks
from twisted.internet.defer import setDebugging

from golem.rpc import cert
from golem.rpc import utils as rpc_utils
from golem.rpc.common import CROSSBAR_DIR, CROSSBAR_PORT
from golem.rpc.mapping.rpcmethodnames import DOCKER_URI
from golem.rpc.router import CrossbarRouter
from golem.rpc.session import (
    ClientProxy,
    Publisher,
    Session,
)
from golem.tools.testwithreactor import TestDirFixtureWithReactor
from golem.tools.testchildprocesses import KillLeftoverChildrenTestMixin

setDebugging(True)

xbar_users = cert.CertificateManager.CrossbarUsers


class MockService():
    def __init__(self):
        self.n_hello_received = 0

    @rpc_utils.expose()
    @classmethod
    def multiply(cls, arg1, arg2):
        return arg1 * arg2

    @rpc_utils.expose()
    @classmethod
    def divide(cls, number, divisor=2):
        return number / divisor

    @rpc_utils.expose()
    @classmethod
    def ping(cls):
        return 'pong'

    @rpc_utils.expose(DOCKER_URI+'.echo')
    @classmethod
    def docker_echo(cls, arg):
        return arg

    @rpc_utils.expose()
    @classmethod
    def non_docker_echo(cls, arg):
        return arg

    @rpc_utils.expose()
    @classmethod
    def exception(cls):
        n = 2
        if n % 2 == 0:
            raise AttributeError("Mock error raised")
        return 2

    def on_hello(self):
        self.n_hello_received += 1


class MockProxy(ClientProxy):  # pylint: disable=too-few-public-methods
    PREFIXES = (
        'tests.golem.rpc.test_router.MockService.',
    )


class _TestRouter(KillLeftoverChildrenTestMixin, TestDirFixtureWithReactor):
    TIMEOUT = 20
    CSRB_FRONTEND: typing.Optional[cert.CertificateManager.CrossbarUsers] = None
    CSRB_BACKEND: typing.Optional[cert.CertificateManager.CrossbarUsers] = None

    # pylint: disable=too-many-instance-attributes
    class State(object):

        def __init__(self):
            self.done = False
            self.errors = []

            self.router = None

            self.backend = MockService()
            self.backend_session = None
            self.frontend = MockService()
            self.frontend_session = None

            self.generate_secrets = True
            self.crsb_frontend_secret = None
            self.crsb_backend_secret = None
            self.subscribe = False

            self.method = None
            self.process = None

        def add_errors(self, *errors):
            print('Errors: {}'.format(pprint.pformat(errors)))
            if errors:
                self.errors += errors
            else:
                self.errors += ['Unknown error']

        def format_errors(self):
            return "\n".join(
                "%d: %s" % (cnt, e) for cnt, e in enumerate(self.errors)
            )

    def setUp(self):
        super().setUp()
        self.state = _TestRouter.State()

    @inlineCallbacks
    def _start_backend_session(self, *_):
        user = self.CSRB_BACKEND
        secret = self.state.crsb_backend_secret

        self.state.backend_session = self.Session(  # pylint: disable=no-member
            self.state.router.address,
            crsb_user=user,
            crsb_user_secret=secret
        )

        yield self.state.backend_session.connect()
        yield self.state.backend_session.add_procedures(
            rpc_utils.object_method_map(
                self.state.backend,
            ),
        )
        yield self._backend_session_started()

    @inlineCallbacks
    def _backend_session_started(self, *_):
        txdefer = self.state.backend_session.register(
            self.state.backend_session.exposed_procedures,
            'sys.exposed_procedures',
        )
        txdefer.addErrback(self.state.add_errors)
        yield txdefer
        user = self.CSRB_FRONTEND
        secret = self.state.crsb_frontend_secret if user else None
        self.state.frontend_session = self.Session(  # pylint: disable=no-member
            self.state.router.address,
            crsb_user=user,
            crsb_user_secret=secret
        )

        txdefer = self.state.frontend_session.connect()
        txdefer.addErrback(self.state.add_errors)
        yield txdefer
        yield self._frontend_session_started()

    def _wait_for_process(self, expect_error=False):
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
            raise Exception(self.state.format_errors())

        if expect_error and not self.state.errors:
            raise Exception("Expected error")
        self.reactor_thread.reactor.stop()

        if self.process.is_alive():
            self.process.terminate()

    def _run_test(self, expect_error, *args, **kwargs):
        self.process = Process(
            target=self.in_subprocess, args=args, kwargs=kwargs
        )
        self.process.daemon = True
        self.process.run()

        self._wait_for_process(expect_error=expect_error)

    def in_subprocess(self, *args, **kwargs):
        deferred = self._start_router(*args, **kwargs)
        deferred.addCallback(lambda *args: print('Router finished', args))
        deferred.addErrback(self.state.add_errors)

    def _start_router(self, *args, **kwargs):
        raise NotImplementedError()

    def _frontend_session_started(self, *_):
        raise NotImplementedError()


class TestRPCNoAuth(_TestRouter):

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
        txdefer = self.state.frontend_session.subscribe(
            self.state.frontend.on_hello,
            'mock.event.hello',
        )
        txdefer.addErrback(self.state.add_errors)
        yield txdefer
        client = MockProxy(self.state.frontend_session)
        yield client._ready
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

    @inlineCallbacks
    def _start_router(self):  # pylint: disable=arguments-differ
        # pylint: disable=no-member
        self.state.router = CrossbarRouter(
            datadir=self.path,
            ssl=False,
            generate_secrets=self.state.generate_secrets
        )
        # set a new role for admin
        self.state.router.config["workers"][0]["transports"][0]["auth"]["anonymous"] = {  # noqa pylint: disable=line-too-long
            "type": "static",
            "role": CrossbarRouter.CrossbarRoles.admin.name
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

        tx_deferred = self.state.router.start(self.reactor_thread.reactor)
        tx_deferred.addErrback(self.state.add_errors)
        yield tx_deferred
        try:
            yield self._start_backend_session()
        except Exception as e:  # pylint: disable=broad-except
            self.state.add_errors(e)


class _TestRPCAuth(_TestRouter):
    DOCKER_METHOD = "docker_echo"
    NON_DOCKER_METHOD = "non_docker_echo"
    TIMEOUT = 10

    @inlineCallbacks
    def _start_router(
            self,
            *args,
            port=CROSSBAR_PORT,
            path=None,
            **kwargs,
    ):  # noqa pylint: disable=arguments-differ
        self.state.subscribe = False
        path = path if path else self.path
        with mock.patch(
            "golem.rpc.cert.CertificateManager.get_secret",
            side_effect=lambda *_: "secret",
        ):
            self.state.router = CrossbarRouter(datadir=path,
                                               ssl=False,
                                               generate_secrets=False,
                                               port=port)
        # pylint: disable=attribute-defined-outside-init
        self.Session = Session

        tx_deferred = self.state.router.start(self.reactor_thread.reactor)
        tx_deferred.addErrback(  # pylint: disable=no-member
            self.state.add_errors,
        )
        yield tx_deferred
        try:
            yield self._start_backend_session()
        except Exception as e:  # pylint: disable=broad-except
            self.state.add_errors(e)

    @inlineCallbacks
    def _frontend_session_started(self, *_):
        client = MockProxy(self.state.frontend_session)
        yield client._ready
        echo_str = "something"
        result = yield getattr(client, self.state.method)(echo_str)
        self.assertEqual(result, echo_str)
        yield self.state.router.stop()
        self.state.done = True

    def _test_rpc_auth_method_access(self, method, error):
        self.state = _TestRouter.State()
        self.state.crsb_frontend_secret = "secret"
        self.state.crsb_backend_secret = "secret"
        self.state.method = method
        self._run_test(error, port=CROSSBAR_PORT, path=self.path)


class TestRPCAuthDockerGolemappDockermethod(_TestRPCAuth):
    CSRB_FRONTEND = xbar_users.docker
    CSRB_BACKEND = xbar_users.golemapp

    def test_rpc_auth_method_access(self):
        self._test_rpc_auth_method_access(
            self.DOCKER_METHOD, False
        )


class TestRPCAuthCliGolemappNondockermethod(_TestRPCAuth):
    CSRB_FRONTEND = xbar_users.golemcli
    CSRB_BACKEND = xbar_users.golemapp

    def test_rpc_auth_method_access(self):
        self._test_rpc_auth_method_access(
            self.NON_DOCKER_METHOD, False
        )


class TestRPCAuthCliGolemappDockermethod(_TestRPCAuth):
    CSRB_FRONTEND = xbar_users.golemcli
    CSRB_BACKEND = xbar_users.golemapp

    def test_rpc_auth_method_access(self):
        self._test_rpc_auth_method_access(
            self.DOCKER_METHOD, False
        )


class TestRPCAuthDockerGolemappNondockermethod(_TestRPCAuth):
    CSRB_FRONTEND = xbar_users.docker
    CSRB_BACKEND = xbar_users.golemapp

    def test_rpc_auth_method_access(self):
        self._test_rpc_auth_method_access(
            self.NON_DOCKER_METHOD, True
        )


class TestRPCAuthCliDockerDockermethod(_TestRPCAuth):
    CSRB_FRONTEND = xbar_users.golemcli
    CSRB_BACKEND = xbar_users.docker

    def test_rpc_auth_method_access(self):
        self._test_rpc_auth_method_access(
            self.DOCKER_METHOD, True
        )


class _TestRPCAuthWrongSecret(_TestRPCAuth):
    CSRB_FRONTEND = xbar_users.golemcli
    CSRB_BACKEND = xbar_users.golemapp

    def setUp(self):
        super().setUp()
        self.cmanager = cert.CertificateManager(
            os.path.join(self.path, CROSSBAR_DIR)
        )

        self.state.router = CrossbarRouter(
            datadir=self.path,
            ssl=False,
            generate_secrets=True,
        )


# pylint: disable=too-many-ancestors
class TestRPCAuthWrongBackendSecret(_TestRPCAuthWrongSecret):
    def test_rpc_auth_wrong_backend_secret(self):
        self.state.crsb_frontend_secret = self.cmanager.get_secret(
            self.CSRB_FRONTEND,
        )
        self.state.crsb_backend_secret = "wrong_secret"
        self._run_test(True, port=CROSSBAR_PORT, path=self.path)


# pylint: disable=too-many-ancestors
class TestRPCAuthWrongFrontendSecret(_TestRPCAuthWrongSecret):
    def test_rpc_auth_wrong_backend_secret(self):
        self.state.crsb_frontend_secret = self.cmanager.get_secret(
            self.CSRB_FRONTEND,
        )
        self.state.crsb_backend_secret = "wrong_secret"
        self._run_test(True, port=CROSSBAR_PORT, path=self.path)
