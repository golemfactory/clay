from mock import Mock

from golem.testutils import TempDirFixture
from golem.tools.assertlogs import LogTestCase

from apps.core.task.verificator import CoreVerificator, SubtaskVerificationState, logger


class TestCoreVerificator(TempDirFixture, LogTestCase):

    def _fill_with_states(self, cv):
        cv.ver_states["SUBTASK UNKNOWN"] = SubtaskVerificationState.UNKNOWN
        cv.ver_states["SUBTASK WAITING"] = SubtaskVerificationState.WAITING
        cv.ver_states["SUBTASK PARTIALLY VERIFIED"] = SubtaskVerificationState.PARTIALLY_VERIFIED
        cv.ver_states["SUBTASK VERIFIED"] = SubtaskVerificationState.VERIFIED
        cv.ver_states["SUBTASK WRONG_ANSWER"] = SubtaskVerificationState.WRONG_ANSWER
        cv.ver_states["another_verified"] = SubtaskVerificationState.VERIFIED

    def test_is_verified(self):
        cv = CoreVerificator()
        assert not cv.is_verified("SUBTASKWHENNOSUBTASKKNOWN")
        self._fill_with_states(cv)

        assert not cv.is_verified("COMPLETELY UNKNOWN")
        assert not cv.is_verified("SUBTASK UNKNOWN")
        assert not cv.is_verified("SUBTASK PARTIALLY VERIFIED")
        assert not cv.is_verified("SUBTASK WRONG ANSWER")
        assert cv.is_verified("SUBTASK VERIFIED")
        assert cv.is_verified("another_verified")

    def test_verification_state(self):

        cv = CoreVerificator()
        with self.assertLogs(logger, level="WARNING"):
            assert cv.get_verification_state("SUBTASKWHENNOSUBTASKKNOWN") == \
                   SubtaskVerificationState.UNKNOWN

        self._fill_with_states(cv)
        with self.assertLogs(logger, level="WARNING"):
            assert cv.get_verification_state("COMPLETELY UNKNOWN") == \
                   SubtaskVerificationState.UNKNOWN

        with self.assertNoLogs(logger, level="WARNING"):
            assert cv.get_verification_state("SUBTASK UNKNOWN") == \
                   SubtaskVerificationState.UNKNOWN

        assert cv.get_verification_state("SUBTASK PARTIALLY VERIFIED") == \
                                         SubtaskVerificationState.PARTIALLY_VERIFIED
        assert cv.get_verification_state("SUBTASK WRONG_ANSWER") == \
                                         SubtaskVerificationState.WRONG_ANSWER
        assert cv.get_verification_state("another_verified") == \
                                         SubtaskVerificationState.VERIFIED
        assert cv.get_verification_state("SUBTASK VERIFIED") == \
                                         SubtaskVerificationState.VERIFIED

    def test_check_files(self):
        cv = CoreVerificator()
        cv._check_files("SUBTASK X", dict(), [], Mock())
        assert cv.get_verification_state("SUBTASK X") == SubtaskVerificationState.WRONG_ANSWER

        files = self.additional_dir_content([3])
        cv._check_files("SUBTASK X2", dict(), files, Mock())
        assert cv.get_verification_state("SUBTASK X2") == SubtaskVerificationState.VERIFIED

        files = self.additional_dir_content([3])
        cv._check_files("SUBTASK Y", dict(), [files[0]], Mock())
        assert cv.get_verification_state("SUBTASK Y") == SubtaskVerificationState.VERIFIED

        cv._check_files("SUBTASK Z", dict(), ["not a file"], Mock())
        assert cv.get_verification_state("SUBTASK Z") == SubtaskVerificationState.WRONG_ANSWER
