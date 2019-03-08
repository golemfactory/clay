from datetime import datetime, timedelta

from freezegun import freeze_time
from twisted.internet.defer import Deferred

from golem.core.deferred import sync_wait
from golem.testutils import TempDirFixture
from golem.verificator.constants import SubtaskVerificationState
from golem.verificator.core_verifier import CoreVerifier


@freeze_time()
class TestCoreVerifier(TempDirFixture):

    def setUp(self):
        super().setUp()
        self.subtask_id = 5
        self.core_verifier = CoreVerifier()
        self.utcnow = datetime.utcnow()

    def test_start_verification(self):
        deferred = Deferred()

        def callback(result):
            subtask_id, state, _answer = result
            assert subtask_id == subtask_info['subtask_id']
            assert state == SubtaskVerificationState.VERIFIED
            deferred.callback(True)

        subtask_info = {'subtask_id': self.subtask_id}
        files = self.additional_dir_content([1])

        verification_data = dict(
            results=files,
            subtask_info=subtask_info,
        )

        finished = self.core_verifier.start_verification(verification_data)
        finished.addCallback(callback)

        assert sync_wait(deferred, 2) is True

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

    def test_task_timeout_when_task_started_and_state_is_active(self):
        for state in CoreVerifier.active_status:
            start_time = self.utcnow - timedelta(hours=1)
            self.core_verifier.time_started = start_time
            self.core_verifier.state = state

            self._verify_task_timeout_results(
                SubtaskVerificationState.NOT_SURE,
                "Verification was stopped",
                start_time,
                self.utcnow
            )

    def test_task_timeout_when_task_started_and_state_is_not_active(self):
        start_time = self.utcnow - timedelta(hours=1)
        self.core_verifier.time_started = start_time

        self._verify_task_timeout_results(
            SubtaskVerificationState.UNKNOWN_SUBTASK,
            "Verification was stopped",
            start_time,
            self.utcnow
        )

    def test_task_timeout_when_task_is_not_started(self):
        self._verify_task_timeout_results(
            SubtaskVerificationState.TIMEOUT,
            "Verification never ran, task timed out",
            self.utcnow,
            self.utcnow,
        )

    def _verify_task_timeout_results(self, expected_state, expected_message,
                                     start_time, end_time):
        returned_subtask_id, state, answer = self.core_verifier.task_timeout(
            self.subtask_id)

        assert returned_subtask_id == self.subtask_id
        assert state == expected_state
        assert answer['message'] == expected_message
        assert answer['time_started'] == start_time
        assert answer['time_ended'] == end_time
