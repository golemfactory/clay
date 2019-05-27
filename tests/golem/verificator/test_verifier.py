from datetime import datetime
from unittest import TestCase

from freezegun import freeze_time

from golem.verificator.verifier import StateVerifier, SubtaskVerificationState


@freeze_time()
class VerifierTest(TestCase):

    @staticmethod
    def test_task_timeout():
        subtask_id = 'abcde'

        def callback(*args, **kwargs):
            time = datetime.utcnow()

            assert kwargs['subtask_id'] == subtask_id
            assert kwargs['verdict'] == SubtaskVerificationState.TIMEOUT
            assert kwargs['result']['time_started'] == time
            assert kwargs['result']['time_ended'] == time

        sv = StateVerifier()
        sv.callback = callback
        sv.task_timeout(subtask_id)
