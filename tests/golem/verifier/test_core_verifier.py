from datetime import datetime, timedelta

from freezegun import freeze_time
from twisted.internet.defer import Deferred

from golem.core.deferred import sync_wait
from golem.testutils import TempDirFixture
from golem.verifier.subtask_verification_state import SubtaskVerificationState
from golem.verifier.core_verifier import CoreVerifier


@freeze_time()
class TestCoreVerifier(TempDirFixture):

    def setUp(self):
        super().setUp()
        self.subtask_id = 5
        files = self.additional_dir_content([1])

        self.subtask_info = {'subtask_id': self.subtask_id}
        self.verification_data = dict(
            results=files,
            subtask_info=self.subtask_info,
        )
        self.core_verifier = CoreVerifier(self.verification_data)
        self.utcnow = datetime.utcnow()

    def test_start_verification(self):
        deferred = Deferred()

        def callback(result):
            subtask_id, state, _answer = result
            assert subtask_id == self.subtask_info['subtask_id']
            assert state == SubtaskVerificationState.VERIFIED
            deferred.callback(True)

        finished = self.core_verifier.start_verification()
        finished.addCallback(callback)

        assert sync_wait(deferred, 2) is True

    def _check_state(self, expected_result: bool):
        core_verifier = CoreVerifier(self.verification_data)
        result = core_verifier.simple_verification()
        assert result is expected_result

    def test_simple_verification(self):

        self.verification_data["results"] = []
        self._check_state(expected_result=False)

        files = self.additional_dir_content([3])
        self.verification_data["results"] = files
        self._check_state(expected_result=True)

        files = self.additional_dir_content([3])
        self.verification_data["results"] = [files[0]]
        self._check_state(expected_result=True)

        self.verification_data["results"] = ["not a file"]
        self._check_state(expected_result=False)

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
