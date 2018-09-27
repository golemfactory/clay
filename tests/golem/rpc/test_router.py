# pylint: disable=protected-access
import time
from threading import Thread

from autobahn.twisted import util
from autobahn.wamp import ApplicationError

from golem.rpc.router import CrossbarRouter
from golem.rpc.session import Session, object_method_map, ClientProxy, Publisher
from golem.tools.testwithreactor import TestDirFixtureWithReactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.defer import setDebugging
setDebugging(True)


class MockService():

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

    @classmethod
    def multiply(cls, arg1, arg2):
        return arg1 * arg2

    @classmethod
    def divide(cls, number, divisor=2):
        return number / divisor

    @classmethod
    def ping(cls):
        return 'pong'

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


TIMEOUT = 40


class TestRouter(TestDirFixtureWithReactor):

    class State(object):

        def __init__(self):
            self.done = False
            self.errors = []

            self.router = None

            self.backend = MockService()
            self.backend_session = None
            self.frontend = MockService()
            self.frontend_session = None

        def add_errors(self, *errors):
            print('Errors: {}'.format(errors))
            if errors:
                self.errors += errors
            else:
                self.errors += ['Unknown error']

    def setUp(self):
        super(TestRouter, self).setUp()
        self.state = TestRouter.State()

    def test_init(self):
        from os.path import join, exists

        crossbar_dir = join(self.path, 'definitely_not_exists')
        router = CrossbarRouter(datadir=crossbar_dir)
        assert exists(crossbar_dir)
        self.assertIsInstance(router, CrossbarRouter)
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

    @inlineCallbacks
    def _start_router(self):
        # pylint: disable=no-member
        self.state.router = CrossbarRouter(datadir=self.path, ssl=False)
        tx_deferred = self.state.router.start(self.reactor_thread.reactor)
        tx_deferred.addErrback(self.state.add_errors)
        yield tx_deferred
        try:
            yield self._start_backend_session()
        except Exception as e:  # pylint: disable=broad-except
            self.state.add_errors(e)

    @inlineCallbacks
    def _start_backend_session(self, *_):
        methods = object_method_map(
            self.state.backend,
            MockService.methods,
        )
        self.state.backend_session = Session(
            self.state.router.address,
            methods=methods,
        )

        txdefer = self.state.backend_session.connect()
        txdefer.addErrback(self.state.add_errors)
        yield txdefer
        yield self._backend_session_started()

    @inlineCallbacks
    def _backend_session_started(self, *_):
        txdefer = self.state.backend_session.register(
            self.state.backend_session.exposed_procedures,
            'sys.exposed_procedures',
        )
        txdefer.addErrback(self.state.add_errors)
        yield txdefer
        self.state.frontend_session = Session(
            self.state.router.address,
            events=object_method_map(
                self.state.frontend,
                MockService.events
            )
        )

        txdefer = self.state.frontend_session.connect()
        txdefer.addErrback(self.state.add_errors)
        yield txdefer
        yield self._frontend_session_started()

    @inlineCallbacks
    def _frontend_session_started(self, *_):
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

    def test_rpc(self):
        thread = Thread(target=self._start_router)
        thread.daemon = True
        thread.start()

        deadline = time.time() + TIMEOUT

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

        if self.state.errors:
            raise Exception(*self.state.errors)
