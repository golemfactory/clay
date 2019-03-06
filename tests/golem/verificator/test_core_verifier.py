from datetime import datetime

from golem.testutils import TempDirFixture
from golem.tools.assertlogs import LogTestCase
from golem.verificator.constants import SubtaskVerificationState
from golem.verificator.core_verifier import CoreVerifier


class TestCoreVerifier(TempDirFixture, LogTestCase):

    def setUp(self):
        super().setUp()
        self.core_verifier = CoreVerifier()

    def test_start_verification(self):
        def callback(result):
            subtask_id, state, _answer = result
            assert subtask_id == subtask_info['subtask_id']
            assert state == SubtaskVerificationState.VERIFIED

        subtask_info = {'subtask_id': 5}
        files = self.additional_dir_content([1])

        verification_data = dict(
            results=files,
            subtask_info=subtask_info,
        )

        finished = self.core_verifier.start_verification(verification_data)
        finished.addCallback(callback)

    def test_simple_verification(self):
        verification_data = dict(
            results=[]
        )
        self.core_verifier.simple_verification(verification_data)
        assert self.core_verifier.state == SubtaskVerificationState.WRONG_ANSWER

        files = self.additional_dir_content([3])
        verification_data["results"] = files
        self.core_verifier.simple_verification(verification_data)
        assert self.core_verifier.state == SubtaskVerificationState.VERIFIED

        verification_data["results"] = [files[0]]
        self.core_verifier.simple_verification(verification_data)
        assert self.core_verifier.state == SubtaskVerificationState.VERIFIED

        verification_data["results"] = ["not a file"]
        self.core_verifier.simple_verification(verification_data)
        assert self.core_verifier.state == SubtaskVerificationState.WRONG_ANSWER

    @staticmethod
    def test_task_timeout():  # TODO: fix it
        subtask_id = 'abcde'

        def callback(*args, **kwargs):
            time = datetime.utcnow()

            assert kwargs['subtask_id'] == subtask_id
            assert kwargs['verdict'] == SubtaskVerificationState.TIMEOUT
            assert kwargs['result']['time_started'] == time
            assert kwargs['result']['time_ended'] == time

        sv = CoreVerifier()
        sv.callback = callback
        sv.task_timeout(subtask_id)
