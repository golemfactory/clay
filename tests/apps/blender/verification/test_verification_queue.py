from unittest import mock
import functools
from twisted.internet.defer import Deferred

from golem.verifier.blender_verifier import BlenderVerifier
from golem.core.common import timeout_to_deadline
from golem.core.deferred import sync_wait
from golem.docker.task_thread import DockerTaskThread
from golem.tools.testwithreactor import TestWithReactor
from apps.core.verification_queue import VerificationQueue


class TestVerificationQueue(TestWithReactor):

    def setUp(self):
        self.queue = VerificationQueue()

    @mock.patch("apps.core.verification_queue.VerificationQueue."
                "_verification_timed_out")
    @mock.patch(
        "golem.verifier.blender_verifier.BlenderVerifier."
        "simple_verification", return_value=True)
    @mock.patch(
        'golem.verifier.blender_verifier.BlenderVerifier.start_rendering')
    def test_task_timeout(self, _start_rendering, _simple_verification,
                          _verification_timed_out, ):

        VerificationQueue.VERIFICATION_TIMEOUT = 2
        d = Deferred()

        def test_timeout():
            subtask_info = {'subtask_id': 'deadbeef'}

            def verification_finished(subtask_id, verdict, result):  # noqa pylint:disable=unused-argument
                d.callback(True)
                return subtask_id

            self.queue.submit(
                functools.partial(BlenderVerifier,
                                  docker_task_cls=DockerTaskThread),
                "deadbeef",
                timeout_to_deadline(10),
                cb=verification_finished,
                subtask_info=subtask_info,
                results=[],
                resources=[],
                reference_data=[],
            )

        reactor = self._get_reactor()
        reactor.callLater(0, test_timeout)

        sync_wait(d, 60)
        _verification_timed_out.assert_called_once()
