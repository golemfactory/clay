import time
from threading import Thread

from golem.rpc.router import CrossbarRouter
from golem.rpc.session import Session, object_method_map, Client
from golem.tools.testwithreactor import TestDirFixtureWithReactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.defer import setDebugging
setDebugging(True)


class MockService(object):

    mapping = dict(
        multiply='mock.multiply',
        divide='mock.divide',
        ping='mock.ping',
    )

    def multiply(self, arg1, arg2):
        return arg1 * arg2

    def divide(self, number, divisor=2):
        return number / divisor

    def ping(self):
        return u'pong'


TIMEOUT = 30


class TestRouter(TestDirFixtureWithReactor):

    class State(object):

        def __init__(self, reactor):
            self.done = False
            self.errors = []

            self.reactor = reactor
            self.router = None

            self.backend = MockService()
            self.frontend = None
            self.backend_session = None
            self.frontend_session = None
            self.backend_deferred = None
            self.frontend_deferred = None

        def add_errors(self, *errors):
            if errors:
                self.errors += errors
            else:
                self.errors += ['Unknown error']

    def setUp(self):
        super(TestRouter, self).setUp()
        self.state = TestRouter.State(self.reactor_thread.reactor)

    def _start_router(self):
        self.state.router = CrossbarRouter(datadir=self.path)
        self.state.router.start(
            self.state.reactor,
            self._start_backend_session, self.state.add_errors
        )

    def _start_backend_session(self, *_):
        self.state.backend_session = Session(
            self.state.router.address,
            object_method_map(
                self.state.backend,
                MockService.mapping
            )
        )

        self.state.backend_deferred = self.state.backend_session.connect()
        self.state.backend_session.ready.addCallbacks(self._backend_session_started, self.state.add_errors)

    def _backend_session_started(self, *_):
        self.state.frontend_session = Session(self.state.router.address)
        self.state.frontend_deferred = self.state.frontend_session.connect()
        self.state.frontend_session.ready.addCallbacks(self._frontend_session_started, self.state.add_errors)

    @inlineCallbacks
    def _frontend_session_started(self, *_):
        self.state.frontend = Client(self.state.frontend_session, MockService.mapping)
        fe = self.state.frontend

        multiply_result = yield fe.multiply(2, 3)
        assert multiply_result == 6

        divide_result = yield fe.divide(4)
        assert divide_result == 2

        divide_result = yield fe.divide(8, 4)
        assert divide_result == 2

        ping_result = yield fe.ping()
        assert ping_result == u'pong'

        self.state.done = True

    def test_rpc(self):
        thread = Thread(target=self._start_router)
        thread.daemon = True
        thread.start()

        started = time.time()

        while True:
            time.sleep(0.5)
            if time.time() > started + TIMEOUT:
                self.state.errors.append(Exception("Test timed out"))

            if self.state.errors or self.state.done:
                break

        self.state.frontend_session.disconnect()
        self.state.backend_session.disconnect()
        time.sleep(0.5)

        if self.state.errors:
            raise Exception(*self.state.errors)
