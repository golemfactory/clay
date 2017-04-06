import time
from threading import Thread

from autobahn.twisted import util
from autobahn.wamp import ApplicationError

from golem.rpc.router import CrossbarRouter
from golem.rpc.session import Session, object_method_map, Client, Publisher
from golem.tools.testwithreactor import TestDirFixtureWithReactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.defer import setDebugging
setDebugging(True)


class MockService(object):

    methods = dict(
        multiply='mock.multiply',
        divide='mock.divide',
        ping='mock.ping',
        exception='mock.exception'
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
        return u'pong'

    def exception(self):
        n = 2
        if n % 2 == 0:
            raise AttributeError("Mock error raised")
        return 2

    def on_hello(self):
        self.n_hello_received += 1


TIMEOUT = 40


class TestRouter(TestDirFixtureWithReactor):

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
            if errors:
                self.errors += errors
            else:
                self.errors += ['Unknown error']

    def setUp(self):
        super(TestRouter, self).setUp()
        self.state = TestRouter.State(self.reactor_thread.reactor)

    def test_init(self):
        from os.path import join, exists

        crossbar_dir = join(self.path, 'definitely_not_exists')
        router = CrossbarRouter(datadir=crossbar_dir)
        assert exists(crossbar_dir)
        self.assertIsInstance(router, CrossbarRouter, "Something went really wrong...")
        self.assertEqual(router.working_dir, join(crossbar_dir, 'crossbar'))

        router = CrossbarRouter(datadir=self.path, crossbar_dir='crozzbar')
        self.assertEqual(router.working_dir, join(self.path, 'crozzbar'))
        self.assertIsNone(router.node)
        self.assertIsNone(router.pubkey)

        tmp_file = join(self.path, 'tmp_file')
        with open(tmp_file, 'w') as f:
            f.write('tmp data')

        with self.assertRaises(IOError):
            CrossbarRouter(crossbar_dir=tmp_file)

    def _start_router(self):
        self.state.router = CrossbarRouter(datadir=self.path)
        self.state.router.start(
            self.state.reactor,
            self._start_backend_session, self.state.add_errors
        )

    def _start_backend_session(self, *_):
        self.state.backend_session = Session(
            self.state.router.address,
            methods=object_method_map(
                self.state.backend,
                MockService.methods
            )
        )

        self.state.backend_deferred = self.state.backend_session.connect()
        self.state.backend_deferred.addCallbacks(self._backend_session_started, self.state.add_errors)

    def _backend_session_started(self, *_):
        self.state.frontend_session = Session(
            self.state.router.address,
            events=object_method_map(
                self.state.frontend,
                MockService.events
            )
        )

        self.state.frontend_deferred = self.state.frontend_session.connect()
        self.state.frontend_deferred.addCallbacks(self._frontend_session_started, self.state.add_errors)

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
        assert ping_result == u'pong'

        yield self.state.router.stop()
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

        if self.state.frontend_session:
            self.state.frontend_session.disconnect()

        if self.state.backend_session:
            self.state.backend_session.disconnect()

        time.sleep(0.5)

        if self.state.errors:
            raise Exception(*self.state.errors)
