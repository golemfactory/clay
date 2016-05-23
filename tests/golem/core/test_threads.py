import unittest

import time
from threading import Thread

from golem.core.threads import ThreadQueueExecutor


class TestThread(Thread):

    def __init__(self, secs, sleep=0.5, group=None,
                 target=None, name=None, args=(),
                 kwargs=None, verbose=None):

        super(TestThread, self).__init__(group, target, name,
                                         args, kwargs, verbose)
        self.working = True
        self.sleep = sleep
        self.secs = secs
        self.called = False

    def run(self):
        self.called = True
        start = time.time()
        while self.working:
            time.sleep(self.sleep)
            if time.time() - start >= self.secs:
                break


class TestThreadExecutor(unittest.TestCase):

    def test_queue(self):
        executor = ThreadQueueExecutor()
        executor.start()

        j1 = TestThread(30)
        j2 = TestThread(30)
        j3 = TestThread(30)

        executor.push(j1)
        assert len(executor._queue) == 1
        executor.push(j2)
        assert len(executor._queue) == 2
        executor.push(j3)
        assert len(executor._queue) == 2
        assert j2 not in executor._queue

        j1.working = False
        j2.working = False
        j3.working = False
        executor.shutdown()

    def test_order(self):
        executor = ThreadQueueExecutor()
        executor.start()

        j1 = TestThread(0)
        j2 = TestThread(0)

        executor.push(j1)
        executor.push(j2)

        time.sleep(2)

        assert j1.called
        assert j2.called
        assert len(executor._queue) == 0

        j1.working = False
        j2.working = False
        executor.shutdown()
