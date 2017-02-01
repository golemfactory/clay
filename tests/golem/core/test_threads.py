import unittest

import time
import threading
from mock import Mock

from golem.core.threads import ThreadQueueExecutor, QueueExecutor


class Thread(threading.Thread):

    def __init__(self, secs, sleep=0.5, group=None,
                 target=None, name=None, args=(),
                 kwargs=None, verbose=None):

        super(Thread, self).__init__(group, target, name,
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


class TestQueueExecutor(unittest.TestCase):

    def test_queue(self):

        method_1 = Mock()
        method_2 = Mock()

        executor = QueueExecutor()

        executor.push(method_1, 0, 1, kw_arg=0)
        executor.push(method_2)

        executor.finish()

        method_1.assert_called_once_with(0, 1, kw_arg=0)
        method_2.assert_called_once_with()

        inner_mock = Mock()

        def method_3():
            inner_mock()
            raise Exception()

        executor.push(method_3)

        executor.finish()

        self.assertTrue(inner_mock.called)


class TestThreadExecutor(unittest.TestCase):

    def test_queue(self):
        executor = ThreadQueueExecutor()
        executor.start = Mock()

        j1 = Thread(30)
        j2 = Thread(30)
        j3 = Thread(30)

        executor.push(j1)
        self.assertEqual(len(executor._queue), 1)
        executor.push(j2)
        self.assertEqual(len(executor._queue), 2)
        executor.push(j3)
        self.assertEqual(len(executor._queue), 2)

        self.assertNotIn(j2, executor._queue)

    def test_order(self):
        executor = ThreadQueueExecutor()

        j1 = Thread(0)
        j2 = Thread(0)

        executor.push(j1)
        executor.push(j2)

        executor.finish()

        self.assertTrue(j1.called)
        self.assertTrue(j2.called)
        self.assertEqual(len(executor._queue), 0)

        j1.working = False
        j2.working = False
        executor.stop()
