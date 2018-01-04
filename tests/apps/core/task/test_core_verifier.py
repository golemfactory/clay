from golem_verificator.core.verifier import CoreVerifier
from golem_verificator.verifier import SubtaskVerificationState

from golem.testutils import TempDirFixture
from golem.tools.assertlogs import LogTestCase



class TestCoreVerifierr(TempDirFixture, LogTestCase):

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
