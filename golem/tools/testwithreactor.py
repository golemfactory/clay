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

    def stop(self):
        result = super(MockReactor, self).stop()
        self._startedBefore = False
        self.running = False
        return result

    def mainLoop(self):
        pass


class MockReactorThread(Thread):
    runner_thread = None

    def __init__(self, _reactor, group=None, name=None, args=(), kwargs=None, verbose=None):

        super(MockReactorThread, self).__init__(group, self.__reactor_loop,
                                                name, args, kwargs, verbose)
        self._reactor = _reactor
        self.working = False

    def start(self):
        self.working = True
        self.runner_thread = Thread(target=self._reactor.run)
        self.runner_thread.daemon = True
        self.runner_thread.start()
        return super(MockReactorThread, self).start()

    def stop(self):
        self.working = False
        if self._reactor.threadpool:
            self._reactor.threadpool.stop()
        self._reactor.stop()

    def __reactor_loop(self):
        while self.working:
            try:
                self._reactor.runUntilCurrent()
                self._reactor.doIteration(self._reactor.timeout() or 0)
            except Exception as e:
                print "Unexpected error in main loop:", e.message


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
        if cls.reactor_thread:
            cls.reactor_thread.stop()
            uninstall_reactor()

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

