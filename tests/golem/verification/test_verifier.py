from unittest import TestCase

from datetime import datetime
from freezegun import freeze_time

from golem.verification.verifier import StateVerifier, \
    SubtaskVerificationState


@freeze_time()
class VerifierTest(TestCase):
    def test_task_timeout(self):
        subtask_id = 'abcde'

        def callback(*args, **kwargs):
            time = datetime.utcnow()

            assert kwargs['subtask_id'] == subtask_id
            assert kwargs['verdict'] == SubtaskVerificationState.TIMEOUT
            assert kwargs['result']['time_started'] == time
            assert kwargs['result']['time_ended'] == time

        sv = StateVerifier(callback)

        sv.task_timeout(subtask_id)
