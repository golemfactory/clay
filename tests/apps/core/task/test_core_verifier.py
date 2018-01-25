from golem.testutils import TempDirFixture
from golem.tools.assertlogs import LogTestCase
from golem.verification.verifier import SubtaskVerificationState

from apps.core.task.verifier import CoreVerifier


class TestCoreVerifierr(TempDirFixture, LogTestCase):

    def test_start_verification(self):
        # given
        def callback(*args, **kwargs):
            pass

        cv = CoreVerifier(callback)
        subtask_info = {'subtask_id': 5}
        files = self.additional_dir_content([1])

        # when
        cv.start_verification(subtask_info, [], [], files)

        # then
        assert cv.state == SubtaskVerificationState.VERIFIED

    def test_check_files(self):
        def callback():
            pass

        cv = CoreVerifier(callback)
        cv._check_files(dict(), [], [], [])
        assert cv.state == SubtaskVerificationState.WRONG_ANSWER

        files = self.additional_dir_content([3])
        cv._check_files(dict(), files, [], [])
        assert cv.state == SubtaskVerificationState.VERIFIED

        files = self.additional_dir_content([3])
        cv._check_files(dict(), [files[0]], [], [])
        assert cv.state == SubtaskVerificationState.VERIFIED

        cv._check_files(dict(), ["not a file"], [], [])
        assert cv.state == SubtaskVerificationState.WRONG_ANSWER
