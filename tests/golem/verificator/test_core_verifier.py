from datetime import datetime

from twisted.internet.defer import Deferred

from golem.core.deferred import sync_wait
from golem.testutils import TempDirFixture
from golem.tools.assertlogs import LogTestCase
from golem.verificator.constants import SubtaskVerificationState
from golem.verificator.core_verifier import CoreVerifier


class TestCoreVerifier(TempDirFixture, LogTestCase):

    def test_start_verification(self):

        d = Deferred()

        def callback(*args, **kwargs):
            assert core_verifier.state == SubtaskVerificationState.VERIFIED
            d.callback(True)

        core_verifier = CoreVerifier()
        subtask_info = {'subtask_id': 5}
        files = self.additional_dir_content([1])

        verification_data = dict()
        verification_data["results"] = files
        verification_data["subtask_info"] = subtask_info

        finished = core_verifier.start_verification(verification_data)
        finished.addCallback(callback)

        sync_wait(d, 40)

    def test_simple_verification(self):
        core_verifier = CoreVerifier()
        subtask_info = {"subtask_id": "2432423"}
        core_verifier.subtask_info = subtask_info
        verification_data = dict()
        verification_data["results"] = []
        core_verifier.simple_verification(verification_data)
        assert core_verifier.state == SubtaskVerificationState.WRONG_ANSWER

        files = self.additional_dir_content([3])
        verification_data["results"] = files
        core_verifier.simple_verification(verification_data)
        assert core_verifier.state == SubtaskVerificationState.VERIFIED

        verification_data["results"] = [files[0]]
        core_verifier.simple_verification(verification_data)
        assert core_verifier.state == SubtaskVerificationState.VERIFIED

        verification_data["results"] = ["not a file"]
        core_verifier.simple_verification(verification_data)
        assert core_verifier.state == SubtaskVerificationState.WRONG_ANSWER

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
