import time
import unittest
from unittest import mock
from twisted.internet.defer import Deferred
from apps.blender.verification_queue import VerificationQueue
from apps.dummy.task.verifier import DummyTaskVerifier
from golem.core.common import timeout_to_deadline
from golem.core.deferred import sync_wait


class TestVerificationQueue(unittest.TestCase):

    def setUp(self):
        self.queue = VerificationQueue()

    @mock.patch('apps.blender.verification_queue.VerificationQueue. \
        _verification_timed_out')
    def test_task_timeout(self, _verification_timed_out):

        from twisted.internet import reactor
        #d = Deferred()

        VerificationQueue.VERIFICATION_TIMEOUT = 2

        self.queue.submit(
            DummyTaskVerifier(),
            "deadbeef",
            timeout_to_deadline(10),
            lambda x: x,
            subtask_info={},
            results=[],
            resources=[],
            reference_data=[]
        )

        time.sleep(5)

        reactor.iterate()

        _verification_timed_out.assert_called_once()
