import imp
import sys
import time
import unittest
from threading import Thread

import twisted
from twisted.internet.selectreactor import SelectReactor
from twisted.internet.task import Clock

from golem.testutils import TempDirFixture as TestDirFixture


__all__ = ['TestWithReactor', 'TestDirFixtureWithReactor']


def replace_reactor():
    try:
        _prev_reactor = imp.find_module('reactor', 'twisted.internet')
    except:
        _prev_reactor = Clock()

    _reactor = MockReactor()
    twisted.internet.reactor = _reactor
    sys.modules['twisted.internet.reactor'] = _reactor
    return _reactor, _prev_reactor


def uninstall_reactor():
    del twisted.internet.reactor
    del sys.modules['twisted.internet.reactor']


class MockReactor(SelectReactor):

    def __init__(self):
        self.threadpool = None
        super(MockReactor, self).__init__()

    def startRunning(self, installSignalHandlers=True):
        self.running = True
        super(MockReactor, self).startRunning(installSignalHandlers=installSignalHandlers)
        self._started = True
        self._stopped = False

    def stop(self):
        if self.running:
            result = super(MockReactor, self).stop()
        else:
            result = False

        self._startedBefore = False
        self.running = False
        return result

    def _handleSignals(self):
        pass

    def mainLoop(self):
        pass


class MockReactorThread(Thread):
    runner_thread = None

    def __init__(self, _reactor, group=None, name=None, args=(), kwargs=None, verbose=None):

        super(MockReactorThread, self).__init__(group, self.__reactor_loop,
                                                name, args, kwargs, verbose)
        self.reactor = _reactor
        self.working = False
        self.done = False

    def start(self):
        self.working = True
        self.done = False
        self.runner_thread = Thread(target=self.reactor.run)
        self.runner_thread.daemon = True
        self.runner_thread.start()
        return super(MockReactorThread, self).start()

    def stop(self):
        self.working = False
        if self.reactor.threadpool:
            self.reactor.threadpool.stop()
        self.reactor.stop()

        while not self.done:
            time.sleep(0.1)

    def __reactor_loop(self):
        timeout = 1 * 10 ** -4
        while self.working:
            try:
                self.reactor.runUntilCurrent()
                self.reactor.doIteration(timeout)
            except Exception as e:
                print "Unexpected error in main loop:", e.message
        self.done = True


class TestWithReactor(unittest.TestCase):
    reactor_thread = None
    prev_reactor = None

    @classmethod
    def setUpClass(cls):
        try:
            _reactor, cls.prev_reactor = replace_reactor()
            _reactor.installed = True
            cls.reactor_thread = MockReactorThread(_reactor)
            cls.reactor_thread.start()
        except Exception as e:
            print "Reactor exception: ", e

    @classmethod
    def tearDownClass(cls):
        if cls.reactor_thread and cls.reactor_thread.isAlive():
            cls.reactor_thread.stop()
            uninstall_reactor()

    @classmethod
    def _get_reactor(cls):
        return cls.reactor_thread.reactor

    @staticmethod
    def _sleep(async, secs=0.5):
        if async:
            time.sleep(secs)


class TestDirFixtureWithReactor(TestDirFixture, TestWithReactor):
    @classmethod
    def setUpClass(cls):
        TestDirFixture.setUpClass()
        TestWithReactor.setUpClass()

    @classmethod
    def tearDownClass(cls):
        TestWithReactor.tearDownClass()
        TestDirFixture.tearDownClass()

