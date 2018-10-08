import unittest
from unittest import mock
import functools
from twisted.internet.defer import Deferred
from golem_verificator.blender_verifier import BlenderVerifier
from golem.core.common import timeout_to_deadline
from golem.docker.task_thread import DockerTaskThread
from apps.blender.verification_queue import VerificationQueue
from apps.blender.blender_reference_generator import BlenderReferenceGenerator


class TestVerificationQueue(unittest.TestCase):

    def setUp(self):
        self.queue = VerificationQueue()

    @mock.patch("apps.blender.verification_queue.VerificationQueue."
                "_verification_timed_out")
    @mock.patch(
        "golem_verificator.blender_verifier.BlenderVerifier."
        "simple_verification", return_value=True)
    @mock.patch('apps.blender.verification_task.VerificationTask.start',
                return_value=Deferred())
    def test_task_timeout(self, _start, _simple_verification,
                          _verification_timed_out, ):

        VerificationQueue.VERIFICATION_TIMEOUT = 2
        from twisted.internet import reactor

        def test_timeout():

            subtask_info = {}
            subtask_info['subtask_id'] = 'deadbeef'

            self.queue.submit(
                functools.partial(BlenderVerifier,
                                  cropper_cls=BlenderReferenceGenerator,
                                  docker_task_cls=DockerTaskThread),
                "deadbeef",
                timeout_to_deadline(10),
                lambda subtask_id, verdict, result: subtask_id,
                subtask_info=subtask_info,
                results=[],
                resources=[],
                reference_data=[]
            )

        reactor.callLater(0, test_timeout)
        reactor.callLater(5, reactor.stop)

        reactor.run()

        _verification_timed_out.assert_called_once()
